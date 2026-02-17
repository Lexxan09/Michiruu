#!/usr/bin/env python3
"""
Bot Telegram XL Axiata Management (FINAL v13 - SESSION ISOLATION FIX)
Features:
1. FIXED: 'No refresh token found' (Decoupled session logic from CLI AuthInstance).
2. FIXED: 'Message is not modified' BadRequest error ignored safely.
3. CORE: Complete Dashboard, Account Manager, QRIS, etc.
"""

import os
import sys
import json
import logging
import asyncio
import hashlib
import time
import uuid
import base64
import requests
from io import BytesIO
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Import qrcode untuk generate gambar
try:
    import qrcode
except ImportError:
    print(
        "Warning: qrcode library not found. Install with: pip install qrcode[pil]"
    )
    qrcode = None

# Load environment variables
load_dotenv()

# Import telegram libraries
try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember, InputFile
    from telegram.ext import (Application, CommandHandler,
                              CallbackQueryHandler, MessageHandler,
                              ContextTypes, filters)
    from telegram.error import TelegramError, BadRequest
except ImportError:
    print(
        "Error: python-telegram-bot tidak terinstall. pip install python-telegram-bot"
    )
    sys.exit(1)

# Import app modules
try:
    from app.service.auth import AuthInstance
    from app.client.engsel import (send_api_request, get_package, get_family,
                                   BASE_API_URL, UA, intercept_page,
                                   get_profile)
    from app.client.encrypt import (API_KEY, build_encrypted_field,
                                    decrypt_xdata, encryptsign_xdata,
                                    get_x_signature_payment,
                                    java_like_timestamp)
    from app.client.ciam import get_otp, submit_otp, get_new_token  # Added get_new_token
except ImportError as e:
    print(f"⚠️ Error Import Module: {e}")
    sys.exit(1)

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO)
logger = logging.getLogger(__name__)

REQUIRED_CHANNEL = os.getenv('REQUIRED_CHANNEL', '@singularityx2')
SESSION_LIFETIME = 86400  # 24 Jam

# Data Decoy
DECOY_CONFIG = {
    "qris_cheap": {
        "family_code": "580c1f94-7dc4-416e-96f6-8faf26567516",
        "variant_code": "b50f954a-696e-46d0-8700-8e4d38521525",
        "price": 1000
    }
}

# XCP Family Codes Configuration
XCP_CONFIG = {
    "xcp_reguler": {
        "name": "XCP REGULER",
        "family_code": "23b71540-8785-4abe-816d-e9b4efa48f95"
    },
    "xcp_addon_15gb": {
        "name": "ADDON 15 GB",
        "family_code": "45c3a622-8c06-4bb1-8e56-bba1f3434600"
    },
    "xcp_addon_10gb": {
        "name": "ADDON 10 GB",
        "family_code": "7658c955-a0b9-405f-bb17-de7f43d1a946"
    }
}

# Additional Package Categories Configuration
PACKAGE_CATEGORIES = {
    "flexmax": {
        "name": "Flexmax",
        "emoji": "🔄",
        "family_code": "2c292a32-7749-4947-8ab2-1d83928eae70"
    },
    "5g_plus": {
        "name": "5G+",
        "emoji": "📡",
        "family_code": "4632cfca-72d8-417e-b790-d7ab3a7825f6"
    },
    "conference": {
        "name": "Conference",
        "emoji": "🎤",
        "family_code": "5dab52d5-6f02-4678-b72f-088396ceb113"
    }
}


# ==========================================
# 🧠 HELPER: SAFE EDIT MESSAGE
# ==========================================
async def safe_edit_message(update: Update,
                            text: str,
                            reply_markup=None,
                            parse_mode='HTML'):
    """
    Prevents 'Message is not modified' error from crashing the bot
    """
    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text=text, reply_markup=reply_markup, parse_mode=parse_mode)
        else:
            await update.message.reply_text(text=text,
                                            reply_markup=reply_markup,
                                            parse_mode=parse_mode)
    except BadRequest as e:
        if "Message is not modified" in str(e):
            pass  # Ignore warning
        else:
            logger.error(f"Telegram BadRequest: {e}")
    except Exception as e:
        logger.error(f"Edit Message Error: {e}")


# ==========================================
# 🧠 VISUAL & DATA HELPERS
# ==========================================


def create_progress_bar(current, total, length=10):
    if total <= 0: percent = 0
    else: percent = current / total
    filled = int(length * percent)
    filled = max(0, min(filled, length))
    bar = "▓" * filled + "░" * (length - filled)
    return f"[{bar} {int(percent * 100)}%]"


def format_quota_display(value, unit_type="DATA"):
    try:
        val = float(value)
        if unit_type == "DATA":
            if val >= 1_073_741_824: return f"{val / 1_073_741_824:.2f} GB"
            elif val >= 1_048_576: return f"{val / 1_048_576:.0f} MB"
            elif val >= 1024: return f"{val / 1024:.0f} KB"
            return f"{val:.0f} B"
        elif unit_type == "VOICE":
            return f"{val / 60:.0f} Menit"
        elif unit_type == "TEXT":
            return f"{int(val)} SMS"
        else:
            return f"{val:.0f}"
    except:
        return str(value)


def mask_msisdn(msisdn):
    s = str(msisdn)
    if len(s) > 8: return s[:5] + "*****" + s[-2:]
    return s


# ==========================================
# 🧠 LOCAL API FETCHERS
# ==========================================


def fetch_balance_api(api_key, tokens):
    path = "api/v8/packages/balance-and-credit"
    payload = {"is_enterprise": False, "lang": "en"}
    try:
        res = send_api_request(api_key, path, payload, tokens["id_token"],
                               "POST")
        if isinstance(res, dict) and res.get("status") == "SUCCESS":
            return res.get("data", {}).get("balance", {})
    except Exception as e:
        logger.error(f"Err Balance: {e}")
    return {}


def fetch_my_packages_api(api_key, tokens):
    path = "api/v8/packages/quota-details"
    payload = {"is_enterprise": False, "lang": "en", "family_member_id": ""}
    try:
        res = send_api_request(api_key, path, payload, tokens["id_token"],
                               "POST")
        if isinstance(res, dict) and res.get("status") == "SUCCESS":
            return res.get("data", {}).get("quotas", [])
        return []
    except Exception as e:
        logger.error(f"Err Packages: {e}")
        return []


# ==========================================
# 🧠 CORE PAYMENT LOGIC
# ==========================================

CODE_MAPPING = {}


def get_short_code(full_code: str) -> str:
    if not full_code: return "invalid"
    short = hashlib.md5(full_code.encode()).hexdigest()[:10]
    CODE_MAPPING[short] = full_code
    return short


def get_full_code(short_code: str) -> str:
    return CODE_MAPPING.get(short_code)


def fetch_package_token(api_key,
                        tokens,
                        code_or_family,
                        is_family=False,
                        variant_code=None):
    try:
        if is_family:
            fam = get_family(api_key, tokens, code_or_family, False)
            if not fam: fam = get_family(api_key, tokens, code_or_family, True)
            if not fam: return None
            for v in fam.get("package_variants", []):
                if not variant_code or v[
                        "package_variant_code"] == variant_code:
                    if v.get("package_options"):
                        opt = v["package_options"][0]
                        return get_package(api_key, tokens,
                                           opt["package_option_code"])
        else:
            return get_package(api_key, tokens, code_or_family)
    except:
        return None


def run_complex_settlement(user_id,
                           method,
                           main_package_code,
                           use_decoy=False,
                           custom_price=None):
    try:
        active_user = get_user_active_session(user_id)
        if not active_user: return False, "Sesi habis/belum login.", {}

        tokens = active_user["tokens"]
        api_key = AuthInstance.api_key

        main_pkg = get_package(api_key, tokens, main_package_code)
        if not main_pkg: return False, "Gagal mengambil data paket utama.", {}

        main_item = {
            "item_code": main_pkg["package_option"]["package_option_code"],
            "item_price": int(main_pkg["package_option"]["price"]),
            "item_name": main_pkg["package_option"]["name"],
            "token_confirmation": main_pkg["token_confirmation"],
            "product_type": ""
        }

        items = []
        token_confirmation_idx = 0

        if use_decoy:
            decoy_conf = DECOY_CONFIG["qris_cheap"]
            decoy_pkg = fetch_package_token(api_key, tokens,
                                            decoy_conf["family_code"], True,
                                            decoy_conf["variant_code"])
            if decoy_pkg:
                decoy_item = {
                    "item_code":
                    decoy_pkg["package_option"]["package_option_code"],
                    "item_price": int(decoy_pkg["package_option"]["price"]),
                    "item_name": decoy_pkg["package_option"]["name"],
                    "token_confirmation": decoy_pkg["token_confirmation"],
                    "product_type": ""
                }
                items.append(decoy_item)
                token_confirmation_idx = 1
            else:
                return False, "Gagal ambil decoy.", {}

        items.append(main_item)
        total_amount = custom_price if (custom_price is not None
                                        and custom_price > 0) else sum(
                                            i['item_price'] for i in items)

        intercept_page(api_key, tokens, items[0]["item_code"], False)

        pay_path = "payments/api/v8/payment-methods-option"
        pay_payload = {
            "payment_type":
            "PURCHASE",
            "is_enterprise":
            False,
            "payment_target":
            items[token_confirmation_idx]["item_code"],
            "lang":
            "en",
            "is_referral":
            False,
            "token_confirmation":
            items[token_confirmation_idx]["token_confirmation"]
        }

        res_pm = send_api_request(api_key, pay_path, pay_payload,
                                  tokens["id_token"], "POST")
        if not isinstance(res_pm, dict) or res_pm.get("status") != "SUCCESS":
            return False, "Gagal init metode bayar.", {}

        token_payment = res_pm["data"]["token_payment"]
        ts_to_sign = res_pm["data"]["timestamp"]

        if method == "PULSA":
            path = "payments/api/v8/settlement-multipayment"
            pay_method_api = "BALANCE"
            add_data = {
                "original_price": items[-1]["item_price"],
                "balance_type": "PREPAID_BALANCE",
                "is_akrab_m2m": False
            }
        elif method == "QRIS":
            path = "payments/api/v8/settlement-multipayment/qris"
            pay_method_api = "QRIS"
            add_data = {"original_price": items[0]["item_price"]}

        full_add_data = {
            "is_spend_limit_temporary": False,
            "migration_type": "",
            "spend_limit_amount": 0,
            "is_spend_limit": False,
            "tax": 0,
            "benefit_type": "",
            "quota_bonus": 0,
            "cashtag": "",
            "is_family_plan": False,
            "combo_details": [],
            "is_switch_plan": False,
            "discount_recurring": 0,
            "has_bonus": False,
            "discount_promo": 0
        }
        full_add_data.update(add_data)

        settlement_payload = {
            "total_discount": 0,
            "is_enterprise": False,
            "payment_token": token_payment if method == "PULSA" else "",
            "token_payment": token_payment if method == "PULSA" else "",
            "activated_autobuy_code": "",
            "cc_payment_type": "",
            "is_myxl_wallet": False,
            "pin": "",
            "ewallet_promo_id": "",
            "members": [],
            "total_fee": 0,
            "fingerprint": "",
            "autobuy": {
                "is_using_autobuy": False,
                "activated_autobuy_code": "",
                "autobuy_threshold_setting": {
                    "label": "",
                    "type": "",
                    "value": 0
                }
            },
            "is_use_point": False,
            "lang": "en",
            "payment_method": pay_method_api,
            "timestamp": ts_to_sign,
            "points_gained": 0,
            "can_trigger_rating": False,
            "akrab": {
                "akrab_members": [],
                "akrab_parent_alias": "",
                "members": []
            },
            "referral_unique_code": "",
            "coupon": "",
            "payment_for": "PACKAGE",
            "with_upsell": False,
            "topup_number": "",
            "stage_token": "",
            "authentication_id": "",
            "encrypted_payment_token": build_encrypted_field(urlsafe_b64=True),
            "token": "",
            "token_confirmation": "",
            "access_token": tokens["access_token"],
            "wallet_number": "",
            "encrypted_authentication_id":
            build_encrypted_field(urlsafe_b64=True),
            "additional_data": full_add_data,
            "total_amount": total_amount,
            "is_using_autobuy": False,
            "items": items
        }

        if method == "QRIS":
            settlement_payload["verification_token"] = token_payment

        encrypted = encryptsign_xdata(api_key, "POST", path,
                                      tokens["id_token"], settlement_payload)
        xtime = int(encrypted["encrypted_body"]["xtime"])
        sig_time_sec = xtime // 1000
        x_requested_at = datetime.fromtimestamp(sig_time_sec,
                                                tz=timezone.utc).astimezone()

        payment_targets = ";".join([i["item_code"] for i in items])
        x_sig = get_x_signature_payment(api_key, tokens["access_token"],
                                        ts_to_sign, payment_targets,
                                        token_payment, pay_method_api,
                                        "PACKAGE", path)

        headers = {
            "host": BASE_API_URL.replace("https://", ""),
            "content-type": "application/json; charset=utf-8",
            "user-agent": UA,
            "x-api-key": API_KEY,
            "authorization": f"Bearer {tokens['id_token']}",
            "x-hv": "v3",
            "x-signature-time": str(sig_time_sec),
            "x-signature": x_sig,
            "x-request-id": str(uuid.uuid4()),
            "x-request-at": java_like_timestamp(x_requested_at),
            "x-version-app": "8.9.0",
        }

        resp = requests.post(f"{BASE_API_URL}/{path}",
                             headers=headers,
                             data=json.dumps(encrypted["encrypted_body"]),
                             timeout=30)

        try:
            res_json = json.loads(resp.text)
            decrypted = decrypt_xdata(api_key, res_json)
            if decrypted["status"] == "SUCCESS":
                return True, "Transaksi Berhasil!", decrypted.get("data", {})
            else:
                return False, decrypted.get("message", "Transaksi Gagal"), {}
        except:
            return False, f"Error Response: {resp.text[:50]}", {}

    except Exception as e:
        logger.error(f"Complex Settlement Error: {e}", exc_info=True)
        return False, str(e), {}


# ==========================================
# 💾 SESSION & SECURITY (ISOLATED)
# ==========================================

USER_DATA_DIR = Path("data/user_data")
USER_DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_user_data_file(user_id):
    user_dir = USER_DATA_DIR / str(user_id)
    user_dir.mkdir(exist_ok=True)
    return user_dir / "refresh-tokens.json"


def check_and_wipe_session(user_id):
    file_path = get_user_data_file(user_id)
    if file_path.exists():
        try:
            if (time.time() - file_path.stat().st_mtime) > SESSION_LIFETIME:
                os.remove(file_path)
                return True
        except:
            pass
    return False


def load_user_tokens(user_id):
    if check_and_wipe_session(user_id): return []
    file_path = get_user_data_file(user_id)
    if file_path.exists():
        with open(file_path, 'r') as f:
            return json.load(f)
    return []


def save_user_tokens(user_id, tokens_list):
    file_path = get_user_data_file(user_id)
    with open(file_path, 'w') as f:
        json.dump(tokens_list, f, indent=2)


def get_user_active_session(user_id):
    """
    ISOLATED SESSION MANAGEMENT
    Avoids using AuthInstance.set_active_user to prevent root-folder conflicts.
    Refreshes token locally if needed.
    """
    tokens_list = load_user_tokens(user_id)
    if not tokens_list: return None

    # Active user is index 0
    active_data = tokens_list[0]
    api_key = AuthInstance.api_key  # API Key is constant

    # Try to refresh token (always ensuring freshness)
    # Using get_new_token from CIAM client directly
    new_tokens = get_new_token(api_key, active_data['refresh_token'],
                               active_data.get('subscriber_id', ''))

    if new_tokens:
        # Update session info
        active_data['refresh_token'] = new_tokens['refresh_token']
        # Also fetch profile to get subscription type if missing
        try:
            profile = get_profile(api_key, new_tokens["access_token"],
                                  new_tokens["id_token"])
            if profile and "profile" in profile:
                active_data['subscriber_id'] = profile["profile"][
                    "subscriber_id"]
                active_data['subscription_type'] = profile["profile"][
                    "subscription_type"]
        except Exception as e:
            logger.warning(f"Profile fetch warning: {e}")

        # Update List and Save
        tokens_list[0] = active_data
        save_user_tokens(user_id, tokens_list)

        return {
            "number": active_data['number'],
            "subscriber_id": active_data.get('subscriber_id'),
            "subscription_type": active_data.get('subscription_type',
                                                 'PREPAID'),
            "tokens": new_tokens
        }
    else:
        # If refresh fails, try using existing if not completely broken, or return None
        logger.error(f"Failed to refresh token for {active_data['number']}")
        return None


def get_package_detail_data(user_id, short_code):
    try:
        active_user = get_user_active_session(user_id)
        if not active_user: return False, "Sesi habis", {}
        tokens = active_user["tokens"]
        full_code = get_full_code(short_code)
        if not full_code: return False, "Kode tidak valid", {}

        pkg = get_package(AuthInstance.api_key, tokens, full_code)
        if not pkg: return False, "Paket tidak ditemukan", {}

        opt = pkg['package_option']

        benefits_list = []
        raw_benefits = opt.get('benefits', [])

        if raw_benefits:
            for b in raw_benefits:
                name = b.get('name', 'Benefit')
                d_type = b.get('data_type', '')
                total = float(b.get('total', 0))
                val_str = "Unlimited" if b.get(
                    'is_unlimited') else format_quota_display(total, d_type)
                benefits_list.append(f"• {name}: {val_str}")
        else:
            benefits_list.append("• Tidak ada info detail benefit")

        detail = {
            'title': opt['name'],
            'price': opt['price'],
            'validity': opt.get('validity', 'N/A'),
            'benefits': benefits_list
        }
        return True, "OK", detail
    except Exception as e:
        logger.error(f"Err Pkg Detail: {e}")
        return False, "Error detail", {}


def get_family_packages_data(user_id, family_code):
    try:
        active_user = get_user_active_session(user_id)
        if not active_user: return False, "Sesi habis", []
        tokens = active_user["tokens"]
        fam = get_family(AuthInstance.api_key, tokens, family_code, False)
        if not fam:
            fam = get_family(AuthInstance.api_key, tokens, family_code, True)
        if not fam: return False, "Family tidak ditemukan", []
        pkgs = []
        for variant in fam.get("package_variants", []):
            for opt in variant.get("package_options", []):
                scode = get_short_code(opt['package_option_code'])
                pkgs.append({
                    'short_code': scode,
                    'name': opt['name'],
                    'price': opt['price']
                })
        return True, "OK", pkgs
    except:
        return False, "Error family", []


# ==========================================
# 🎮 HANDLERS
# ==========================================
async def check_channel_membership(update, context):
    user_id = update.effective_user.id
    try:
        member = await context.bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in [
            ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.OWNER
        ]
    except:
        return False


async def show_join_alert(update):
    msg = f"⛔ Akses Ditolak. Join {REQUIRED_CHANNEL} dulu."
    kb = [[
        InlineKeyboardButton(
            "📢 Join Channel",
            url=f"https://t.me/{REQUIRED_CHANNEL.replace('@','')}")
    ], [InlineKeyboardButton("✅ Check", callback_data="main_menu")]]
    if update.callback_query:
        await update.callback_query.answer("Wajib Join!", show_alert=True)
    else:
        await update.message.reply_text(msg,
                                        reply_markup=InlineKeyboardMarkup(kb))


async def start(update, context):
    if not await check_channel_membership(update, context):
        return await show_join_alert(update)
    await show_main_menu(update, context)


async def show_main_menu(update, context):
    user_id = update.effective_user.id
    active_user = get_user_active_session(user_id)

    if not active_user:
        kb = [[
            InlineKeyboardButton("➕ Login (Add Account)",
                                 callback_data="add_account")
        ]]
        text = "⚠️ <b>Belum Login</b>\nSilakan login dulu."
        await safe_edit_message(update,
                                text,
                                reply_markup=InlineKeyboardMarkup(kb))
    else:
        tokens = active_user["tokens"]
        api_key = AuthInstance.api_key

        balance = fetch_balance_api(api_key, tokens)
        packages = fetch_my_packages_api(api_key, tokens)

        msisdn = mask_msisdn(active_user.get("number", "Unknown"))
        sub_type = active_user.get("subscription_type", "UNKNOWN")

        exp_date_ts = balance.get("expired_at", 0)
        exp_date = datetime.fromtimestamp(exp_date_ts).strftime('%Y-%m-%d')
        grace_date = (datetime.fromtimestamp(exp_date_ts) +
                      timedelta(days=30)).strftime('%Y-%m-%d')
        pulsa = balance.get("remaining", 0)

        dash = f"📡 <b>INFO KARTU XL</b>\n"
        dash += f"├ Nomor: <code>{msisdn}</code>\n"
        dash += f"├ Tipe: {sub_type}\n"
        dash += f"├ Masa Aktif: {exp_date}\n"
        dash += f"├ Tenggang: {grace_date}\n"
        dash += f"└ <b>Pulsa: Rp {pulsa:,}</b>\n\n"
        dash += "📦 <b>DETAIL KUOTA AKTIF:</b>\n"

        if not packages:
            dash += "<i>Tidak ada paket aktif.</i>"
        else:
            for pkg in packages:
                pkg_name = pkg.get("name", "Unknown Package")
                dash += f"\n<b>{pkg_name}</b>\n"
                benefits = pkg.get("benefits", [])
                if not benefits:
                    dash += "  └ <i>Tidak ada detail benefit</i>\n"
                for b in benefits:
                    b_name = b.get("name", "Quota")
                    rem = float(b.get("remaining", 0))
                    total = float(b.get("total", 0))
                    d_type = b.get("data_type", "DATA")
                    display_rem = format_quota_display(rem, d_type)
                    display_tot = format_quota_display(total, d_type)
                    dash += f"  • {b_name}: {display_rem} / {display_tot}\n"
                    if d_type == "DATA":
                        dash += f"  • {create_progress_bar(rem, total)}\n"

        kb = [[
            InlineKeyboardButton("🔍 Cari Paket", callback_data="search_menu"),
            InlineKeyboardButton("🔥 Hot Deals", callback_data="hot_deals")
        ],
              [
                  InlineKeyboardButton("🛒 Beli (Family)",
                                       callback_data="buy_menu"),
                  InlineKeyboardButton("📱 XCP", callback_data="xcp_menu")
              ],
              [
                  InlineKeyboardButton("🔄 Flexmax",
                                       callback_data="flexmax_menu"),
                  InlineKeyboardButton("📡 5G+", callback_data="5g_plus_menu")
              ],
              [
                  InlineKeyboardButton("🎤 Conference",
                                       callback_data="conference_menu"),
                  InlineKeyboardButton("👤 Akun",
                                       callback_data="account_manager")
              ],
              [
                  InlineKeyboardButton("🔄 Refresh Dashboard",
                                       callback_data="main_menu")
              ]]
        await safe_edit_message(update,
                                dash[:4000],
                                reply_markup=InlineKeyboardMarkup(kb))


async def button_handler(update, context):
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id

    if not await check_channel_membership(update, context):
        return await show_join_alert(update)

    if data == "main_menu":
        context.user_data['state'] = None
        return await show_main_menu(update, context)

    elif data == "account_manager":
        return await show_account_manager(update, context)

    elif data.startswith("switch_acc_"):
        tgt = int(data.split("_")[2])
        tokens = load_user_tokens(user_id)
        new_l = [t for t in tokens if t['number'] == tgt
                 ] + [t for t in tokens if t['number'] != tgt]
        save_user_tokens(user_id, new_l)
        await query.answer("Akun diganti!")
        return await show_main_menu(update, context)

    elif data.startswith("del_acc_"):
        tgt = int(data.split("_")[2])
        tokens = load_user_tokens(user_id)
        new_l = [t for t in tokens if t['number'] != tgt]
        save_user_tokens(user_id, new_l)
        await query.answer("Akun dihapus!")
        if not new_l: return await show_main_menu(update, context)
        return await show_account_manager(update, context)

    elif data == "search_menu" or data == "buy_menu":
        kb = [[
            InlineKeyboardButton("🔍 Input Family Code",
                                 callback_data="input_family")
        ], [InlineKeyboardButton("Back", callback_data="main_menu")]]
        await safe_edit_message(update,
                                "🔍 Pilih metode:",
                                reply_markup=InlineKeyboardMarkup(kb))

    elif data == "input_family":
        context.user_data['state'] = 'search_family'
        await safe_edit_message(update, "⌨️ <b>Kirim Family Code:</b>")

    elif data.startswith("pkg_"):
        scode = data.replace("pkg_", "")
        suc, msg, detail = get_package_detail_data(user_id, scode)
        if not suc:
            await safe_edit_message(
                update,
                "❌ Gagal load detail.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("Back",
                                           callback_data="main_menu")]]))
            return

        benefits_txt = "\n".join(detail['benefits'])
        txt = (
            f"🛒 <b>{detail['title']}</b>\n💰 Rp {detail['price']:,} | ⏳ {detail['validity']}\n\n🎁 <b>Benefits:</b>\n{benefits_txt}"
        )

        kb = [[
            InlineKeyboardButton("💳 Pulsa",
                                 callback_data=f"pay_PULSA_0_{scode}"),
            InlineKeyboardButton("💳 Pulsa+Decoy",
                                 callback_data=f"pay_PULSA_1_{scode}")
        ],
              [
                  InlineKeyboardButton("📱 QRIS",
                                       callback_data=f"ask_QRIS_0_{scode}"),
                  InlineKeyboardButton("📱 QRIS+Decoy",
                                       callback_data=f"ask_QRIS_1_{scode}")
              ], [InlineKeyboardButton("❌ Batal", callback_data="main_menu")]]
        await safe_edit_message(update,
                                txt,
                                reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("ask_QRIS_"):
        context.user_data['trx_pending'] = {
            'method': 'QRIS',
            'use_decoy': data.split("_")[2] == "1",
            'scode': data.split("_")[3]
        }
        context.user_data['state'] = 'wait_price_input'
        kb = [[
            InlineKeyboardButton("❌ Batal", callback_data="cancel_overwrite")
        ]]
        await safe_edit_message(
            update,
            "🛠 <b>OVERWRITE HARGA</b>\nKirim harga manual (cth: 20000) atau ketik 'cancel'.",
            reply_markup=InlineKeyboardMarkup(kb))

    elif data == "cancel_overwrite":
        context.user_data['state'] = None
        await safe_edit_message(
            update,
            "❌ Dibatalkan.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Menu", callback_data="main_menu")]]))

    elif data.startswith("pay_PULSA_"):
        parts = data.split("_")
        await process_transaction(update, context, user_id, "PULSA",
                                  get_full_code(parts[3]), parts[2] == "1",
                                  None)

    elif data == "add_account":
        context.user_data['state'] = 'add_otp'
        await safe_edit_message(
            update,
            "⌨️ Masukkan Nomor HP:",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Batal",
                                       callback_data="main_menu")]]))

    elif data == "xcp_menu":
        kb = [[
            InlineKeyboardButton("📶 XCP REGULER", callback_data="xcp_reguler")
        ], [
            InlineKeyboardButton("➕ XCP ADDON", callback_data="xcp_addon_menu")
        ], [InlineKeyboardButton("🔙 Kembali", callback_data="main_menu")]]
        await safe_edit_message(update,
                                "📱 <b>Menu XCP</b>\nPilih kategori paket:",
                                reply_markup=InlineKeyboardMarkup(kb))

    elif data == "xcp_reguler":
        await show_xcp_packages(update, context, user_id, "xcp_reguler")

    elif data == "xcp_addon_menu":
        kb = [[
            InlineKeyboardButton("📦 ADDON 15 GB",
                                 callback_data="xcp_addon_15gb")
        ],
              [
                  InlineKeyboardButton("📦 ADDON 10 GB",
                                       callback_data="xcp_addon_10gb")
              ], [InlineKeyboardButton("🔙 Kembali", callback_data="xcp_menu")]]
        await safe_edit_message(update,
                                "➕ <b>XCP ADDON</b>\nPilih paket addon:",
                                reply_markup=InlineKeyboardMarkup(kb))

    elif data == "xcp_addon_15gb":
        await show_xcp_packages(update, context, user_id, "xcp_addon_15gb")

    elif data == "xcp_addon_10gb":
        await show_xcp_packages(update, context, user_id, "xcp_addon_10gb")

    elif data == "flexmax_menu":
        await show_category_packages(update, context, user_id, "flexmax")

    elif data == "5g_plus_menu":
        await show_category_packages(update, context, user_id, "5g_plus")

    elif data == "conference_menu":
        await show_category_packages(update, context, user_id, "conference")

    else:
        await safe_edit_message(
            update,
            "Coming Soon",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Back", callback_data="main_menu")]]))


async def show_xcp_packages(update, context, user_id, xcp_type):
    """
    Menampilkan daftar paket XCP berdasarkan tipe
    xcp_type: 'xcp_reguler', 'xcp_addon_15gb', atau 'xcp_addon_10gb'
    """
    xcp_info = XCP_CONFIG.get(xcp_type)
    if not xcp_info:
        await safe_edit_message(
            update,
            "❌ Konfigurasi XCP tidak ditemukan",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Kembali",
                                       callback_data="xcp_menu")]]))
        return

    # Show loading message
    await safe_edit_message(update,
                            f"🔍 Mencari paket <b>{xcp_info['name']}</b>...",
                            parse_mode='HTML')

    # Fetch packages from family code
    family_code = xcp_info['family_code']
    suc, msg, pkgs = get_family_packages_data(user_id, family_code)

    if not suc or not pkgs:
        kb = [[InlineKeyboardButton("🔙 Kembali", callback_data="xcp_menu")]]
        await safe_edit_message(
            update,
            f"❌ Gagal memuat paket {xcp_info['name']}\n{msg}",
            reply_markup=InlineKeyboardMarkup(kb))
        return

    # Build keyboard with numbered packages
    kb = []
    header_text = f"📱 <b>{xcp_info['name']}</b>\n\n"
    header_text += f"🔍 Ditemukan {len(pkgs)} paket:\n\n"

    for idx, p in enumerate(pkgs, 1):
        # Format package name with number
        pkg_name = p['name']
        pkg_price = f"Rp {p['price']:,}"

        # Add number prefix if it's XCP REGULER
        if xcp_type == "xcp_reguler":
            display_name = f"{idx}. {pkg_name} - {pkg_price}"
        else:
            display_name = f"{pkg_name} - {pkg_price}"

        kb.append([
            InlineKeyboardButton(display_name,
                                 callback_data=f"pkg_{p['short_code']}")
        ])

    # Add back button based on context
    if xcp_type == "xcp_reguler":
        kb.append(
            [InlineKeyboardButton("🔙 Kembali", callback_data="xcp_menu")])
    else:
        kb.append([
            InlineKeyboardButton("🔙 Kembali", callback_data="xcp_addon_menu")
        ])

    await safe_edit_message(update,
                            header_text,
                            reply_markup=InlineKeyboardMarkup(kb))


async def show_category_packages(update, context, user_id, category_key):
    """
    Menampilkan daftar paket dari kategori umum (Flexmax, 5G+, Conference)
    category_key: 'flexmax', '5g_plus', atau 'conference'
    """
    category_info = PACKAGE_CATEGORIES.get(category_key)
    if not category_info:
        await safe_edit_message(update,
                                "❌ Konfigurasi kategori tidak ditemukan",
                                reply_markup=InlineKeyboardMarkup([[
                                    InlineKeyboardButton(
                                        "🔙 Kembali", callback_data="main_menu")
                                ]]))
        return

    # Show loading message
    emoji = category_info.get('emoji', '📦')
    name = category_info['name']
    await safe_edit_message(update,
                            f"🔍 Mencari paket <b>{emoji} {name}</b>...",
                            parse_mode='HTML')

    # Fetch packages from family code
    family_code = category_info['family_code']
    suc, msg, pkgs = get_family_packages_data(user_id, family_code)

    if not suc or not pkgs:
        kb = [[InlineKeyboardButton("🔙 Kembali", callback_data="main_menu")]]
        await safe_edit_message(update,
                                f"❌ Gagal memuat paket {name}\n{msg}",
                                reply_markup=InlineKeyboardMarkup(kb))
        return

    # Build keyboard with packages
    kb = []
    header_text = f"{emoji} <b>{name}</b>\n\n"
    header_text += f"🔍 Ditemukan {len(pkgs)} paket:\n\n"

    for idx, p in enumerate(pkgs, 1):
        pkg_name = p['name']
        pkg_price = f"Rp {p['price']:,}"
        display_name = f"{idx}. {pkg_name} - {pkg_price}"
        kb.append([
            InlineKeyboardButton(display_name,
                                 callback_data=f"pkg_{p['short_code']}")
        ])

    # Add back button
    kb.append(
        [InlineKeyboardButton("🔙 Kembali ke Menu", callback_data="main_menu")])

    await safe_edit_message(update,
                            header_text,
                            reply_markup=InlineKeyboardMarkup(kb))


async def show_account_manager(update, context):
    user_id = update.effective_user.id
    tokens = load_user_tokens(user_id)
    kb = []
    for idx, t in enumerate(tokens):
        msisdn = mask_msisdn(t['number'])
        status = "✅" if idx == 0 else ""
        kb.append([
            InlineKeyboardButton(f"{status} {msisdn}",
                                 callback_data=f"switch_acc_{t['number']}")
        ])
        kb.append([
            InlineKeyboardButton(f"🗑 Hapus {msisdn}",
                                 callback_data=f"del_acc_{t['number']}")
        ])

    kb.append(
        [InlineKeyboardButton("➕ Tambah Akun", callback_data="add_account")])
    kb.append(
        [InlineKeyboardButton("🔙 Menu Utama", callback_data="main_menu")])
    await safe_edit_message(update,
                            "👤 <b>Account Manager</b>",
                            reply_markup=InlineKeyboardMarkup(kb))


async def process_transaction(update, context, user_id, method, full_code,
                              use_decoy, custom_price):

    async def send_msg(text, **kwargs):
        if update.message:
            return await update.message.reply_text(text, **kwargs)
        else:
            return await update.callback_query.edit_message_text(
                text, **kwargs)

    await send_msg(f"⏳ Memproses {method}...", parse_mode='HTML')
    suc, msg, data = run_complex_settlement(user_id, method, full_code,
                                            use_decoy, custom_price)

    if suc:
        txt = f"✅ <b>SUKSES!</b>\n📦 Paket: {full_code}\n"
        if method == "QRIS":
            trx_id = data.get("transaction_code")
            if trx_id:
                active_user = get_user_active_session(user_id)
                res_qr = send_api_request(
                    AuthInstance.api_key, "payments/api/v8/pending-detail", {
                        "transaction_id": trx_id,
                        "is_enterprise": False,
                        "lang": "en",
                        "status": ""
                    }, active_user["tokens"]["id_token"], "POST")
                qr_str = res_qr.get("data", {}).get("qr_code") if isinstance(
                    res_qr, dict) else None

                if qr_str:
                    if qrcode:
                        qr = qrcode.QRCode()
                        qr.add_data(qr_str)
                        qr.make()
                        img = qr.make_image(fill="black", back_color="white")
                        bio = BytesIO()
                        img.save(bio, 'PNG')
                        bio.seek(0)
                        await context.bot.send_photo(chat_id=user_id,
                                                     photo=bio,
                                                     caption="📱 Scan QRIS")
                    else:
                        txt += f"\nQR String: {qr_str[:50]}..."

        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Menu", callback_data="main_menu")]])
        if update.message:
            await update.message.reply_text(txt,
                                            reply_markup=kb,
                                            parse_mode='HTML')
        else:
            await update.callback_query.edit_message_text(txt,
                                                          reply_markup=kb,
                                                          parse_mode='HTML')
    else:
        await send_msg(f"❌ <b>GAGAL</b>\n{msg}",
                       reply_markup=InlineKeyboardMarkup([[
                           InlineKeyboardButton("Menu",
                                                callback_data="main_menu")
                       ]]),
                       parse_mode='HTML')


async def message_handler(update, context):
    user_id = update.effective_user.id
    state = context.user_data.get('state')
    text = update.message.text

    if state == 'search_family':
        suc, msg, pkgs = get_family_packages_data(user_id, text)
        if not suc: await update.message.reply_text(f"❌ {msg}")
        else:
            kb = []
            for p in pkgs:
                kb.append([
                    InlineKeyboardButton(
                        f"{p['name']} - {p['price']}",
                        callback_data=f"pkg_{p['short_code']}")
                ])
            kb.append(
                [InlineKeyboardButton("Cancel", callback_data="main_menu")])
            await update.message.reply_text(
                f"Hasil: {text}", reply_markup=InlineKeyboardMarkup(kb))
        context.user_data['state'] = None

    elif state == 'wait_price_input':
        if text.lower() == 'cancel':
            context.user_data['state'] = None
            await update.message.reply_text(
                "Batal.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("Menu",
                                           callback_data="main_menu")]]))
            return
        try:
            price = int(text)
            trx = context.user_data.get('trx_pending')
            await process_transaction(update, context, user_id, trx['method'],
                                      get_full_code(trx['scode']),
                                      trx['use_decoy'], price)
        except:
            await update.message.reply_text("Angka salah/cancel.")
        context.user_data['state'] = None

    elif state == 'add_otp':
        sid = get_otp(text)
        if sid:
            context.user_data.update({
                'temp_phone': text,
                'state': 'submit_otp'
            })
            await update.message.reply_text("✅ OTP Dikirim!")
        else:
            await update.message.reply_text("❌ Gagal OTP")

    elif state == 'submit_otp':
        phone = context.user_data.get('temp_phone')
        tokens = submit_otp(AuthInstance.api_key, "SMS", phone, text)
        if tokens:
            saved = load_user_tokens(user_id)
            # Add to saved list locally, don't use AuthInstance.set_active_user yet
            # because we are in isolated mode
            new_entry = {
                'number': int(phone),
                'refresh_token': tokens['refresh_token']
            }

            # Check if exists and update/insert
            existing_idx = next((i for i, item in enumerate(saved)
                                 if item["number"] == int(phone)), -1)
            if existing_idx != -1:
                saved.pop(existing_idx)

            saved.insert(0, new_entry)
            save_user_tokens(user_id, saved)

            await update.message.reply_text(
                "Login Sukses!",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("Menu",
                                           callback_data="main_menu")]]))
        else:
            await update.message.reply_text("OTP Salah")
        context.user_data['state'] = None


def main():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", lambda u, c: show_main_menu(u, c)))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    print("Bot Running...")
    app.run_polling()


if __name__ == '__main__':
    main()
