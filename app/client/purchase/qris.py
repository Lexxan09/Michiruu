from datetime import datetime, timezone
import json
import uuid
import base64
import time
import shutil
import requests
import qrcode

from app.client.engsel import *
from app.client.encrypt import (
    API_KEY,
    decrypt_xdata,
    encryptsign_xdata,
    java_like_timestamp,
    get_x_signature_payment
)
from app.type_dict import PaymentItem


# =====================================================
# UI UTIL (AMAN – TIDAK SENTUH LOGIC PEMBAYARAN)
# =====================================================

ORANGE = "\033[38;2;255;165;0m"
RESET = "\033[0m"


def term_width(default=80):
    try:
        return shutil.get_terminal_size().columns
    except Exception:
        return default


def print_box(title: str):
    w = max(40, term_width())
    line = "─" * (w - 2)
    print(f"{ORANGE}┌{line}┐{RESET}")
    print(f"{ORANGE}│{title.center(w - 2)}│{RESET}")
    print(f"{ORANGE}└{line}┘{RESET}")


# =====================================================
# CORE LOGIC (ASLI – JANGAN DIUBAH)
# =====================================================

def settlement_qris(
    api_key: str,
    tokens: dict,
    items: list[PaymentItem],
    payment_for: str,
    ask_overwrite: bool,
    overwrite_amount: int = -1,
    token_confirmation_idx: int = 0,
    amount_idx: int = -1,
    topup_number: str = "",
    stage_token: str = "",
):
    if overwrite_amount == -1 and not ask_overwrite:
        print("Either ask_overwrite must be True or overwrite_amount must be set.")
        return None

    token_confirmation = items[token_confirmation_idx]["token_confirmation"]

    payment_targets = ""
    for item in items:
        if payment_targets:
            payment_targets += ";"
        payment_targets += item["item_code"]

    amount_int = 0
    if overwrite_amount != -1:
        amount_int = overwrite_amount
    elif amount_idx == -1:
        amount_int = items[amount_idx]["item_price"]

    if ask_overwrite:
        print(f"Total amount is {amount_int}.")
        new_amount = input("Enter new amount or press Enter to continue: ")
        if new_amount.strip():
            try:
                amount_int = int(new_amount)
            except ValueError:
                print("Invalid input, using original amount.")

    intercept_page(api_key, tokens, items[0]["item_code"], False)

    print("Getting payment methods...")
    payment_res = send_api_request(
        api_key,
        "payments/api/v8/payment-methods-option",
        {
            "payment_type": "PURCHASE",
            "is_enterprise": False,
            "payment_target": items[token_confirmation_idx]["item_code"],
            "lang": "en",
            "is_referral": False,
            "token_confirmation": token_confirmation,
        },
        tokens["id_token"],
        "POST",
    )

    if payment_res["status"] != "SUCCESS":
        print("Failed to fetch payment methods.")
        return None

    token_payment = payment_res["data"]["token_payment"]
    ts_to_sign = payment_res["data"]["timestamp"]

    path = "payments/api/v8/settlement-multipayment/qris"

    settlement_payload = {
        "akrab": {
            "akrab_members": [],
            "akrab_parent_alias": "",
            "members": []
        },
        "can_trigger_rating": False,
        "total_discount": 0,
        "coupon": "",
        "payment_for": payment_for,
        "topup_number": topup_number,
        "stage_token": stage_token,
        "is_enterprise": False,
        "autobuy": {
            "is_using_autobuy": False,
            "activated_autobuy_code": "",
            "autobuy_threshold_setting": {
                "label": "",
                "type": "",
                "value": 0
            }
        },
        "access_token": tokens["access_token"],
        "is_myxl_wallet": False,
        "additional_data": {
            "original_price": items[0]["item_price"],
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
        },
        "total_amount": amount_int,
        "total_fee": 0,
        "is_use_point": False,
        "lang": "en",
        "items": items,
        "verification_token": token_payment,
        "payment_method": "QRIS",
        "timestamp": int(time.time()),
    }

    encrypted = encryptsign_xdata(
        api_key, "POST", path, tokens["id_token"], settlement_payload
    )

    xtime = int(encrypted["encrypted_body"]["xtime"])
    sig_time_sec = xtime // 1000
    x_requested_at = datetime.fromtimestamp(
        sig_time_sec, tz=timezone.utc
    ).astimezone()

    headers = {
        "host": BASE_API_URL.replace("https://", ""),
        "content-type": "application/json; charset=utf-8",
        "user-agent": UA,
        "x-api-key": API_KEY,
        "authorization": f"Bearer {tokens['id_token']}",
        "x-hv": "v3",
        "x-signature-time": str(sig_time_sec),
        "x-signature": get_x_signature_payment(
            api_key,
            tokens["access_token"],
            ts_to_sign,
            payment_targets,
            token_payment,
            "QRIS",
            payment_for,
            path,
        ),
        "x-request-id": str(uuid.uuid4()),
        "x-request-at": java_like_timestamp(x_requested_at),
        "x-version-app": "8.9.0",
    }

    print("Sending settlement request...")
    resp = requests.post(
        f"{BASE_API_URL}/{path}",
        headers=headers,
        data=json.dumps(encrypted["encrypted_body"]),
        timeout=30,
    )

    try:
        body = decrypt_xdata(api_key, json.loads(resp.text))
        if body["status"] != "SUCCESS":
            print("Settlement failed.")
            return None
        return body["data"]["transaction_code"]
    except Exception as e:
        print("[decrypt err]", e)
        return None


def get_qris_code(api_key, tokens, transaction_id):
    res = send_api_request(
        api_key,
        "payments/api/v8/pending-detail",
        {
            "transaction_id": transaction_id,
            "is_enterprise": False,
            "lang": "en",
            "status": "",
        },
        tokens["id_token"],
        "POST",
    )
    return res["data"]["qr_code"] if res["status"] == "SUCCESS" else None


# =====================================================
# UI WRAPPER (AMAN)
# =====================================================

def show_qris_payment(
    api_key,
    tokens,
    items,
    payment_for,
    ask_overwrite,
    overwrite_amount=-1,
    token_confirmation_idx=0,
    amount_idx=-1,
    topup_number="",
    stage_token="",
):
    tx_id = settlement_qris(
        api_key,
        tokens,
        items,
        payment_for,
        ask_overwrite,
        overwrite_amount,
        token_confirmation_idx,
        amount_idx,
        topup_number,
        stage_token,
    )

    if not tx_id:
        print("Failed to create QRIS transaction.")
        return

    print()
    print_box("📱  QRIS PEMBAYARAN  📱")
    print("Fetching QRIS code...\n")

    qris_code = get_qris_code(api_key, tokens, tx_id)
    if not qris_code:
        print("Failed to get QRIS code.")
        return

    print_box("SCAN QR DI BAWAH INI")
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=1,
        border=1,
    )
    qr.add_data(qris_code)
    qr.make(fit=True)
    qr.print_ascii(invert=True)
    print()

    qris_b64 = base64.urlsafe_b64encode(qris_code.encode()).decode()
    qris_url = f"https://ki-ar-kod.netlify.app/?data={qris_b64}"

    print_box("ALTERNATIF LINK QRIS")
    print(qris_url)
    print()
    input("Silahkan lakukan pembayaran & cek hasil pembelian di aplikasi MyXL.\nTekan Enter untuk kembali...")
