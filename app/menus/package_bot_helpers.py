"""
Helper functions untuk Bot Telegram - Non-Interactive Version
FIXED: Callback data shortened to avoid Button_data_invalid error
"""
import json
import hashlib
from typing import Dict, List, Optional, Tuple
from app.service.auth import AuthInstance
from app.client.engsel import (
    send_api_request, 
    get_package, 
    get_family,
    get_addons
)
from app.menus.util import format_quota_byte

# Global storage untuk mapping short code ke full quota code
# Ini akan menyimpan mapping sementara selama bot running
CODE_MAPPING = {}

def get_short_code(full_code: str) -> str:
    """
    Generate short code (max 20 chars) dari full code untuk callback_data
    Menggunakan hash untuk uniqueness
    """
    # Simpan mapping
    short = hashlib.md5(full_code.encode()).hexdigest()[:16]
    CODE_MAPPING[short] = full_code
    return short

def get_full_code(short_code: str) -> Optional[str]:
    """Get full code from short code"""
    return CODE_MAPPING.get(short_code)


def get_my_packages_data() -> Tuple[bool, str, List[Dict]]:
    """
    Mengambil data my packages tanpa interaksi user
    
    Returns:
        Tuple[bool, str, List[Dict]]: (success, message, packages_list)
    """
    try:
        api_key = AuthInstance.api_key
        tokens = AuthInstance.get_active_tokens()
        
        if not tokens:
            return False, "❌ Tidak ada akun aktif.", []
        
        id_token = tokens.get("id_token")
        path = "api/v8/packages/quota-details"
        
        payload = {
            "is_enterprise": False,
            "lang": "en",
            "family_member_id": ""
        }
        
        res = send_api_request(api_key, path, payload, id_token, "POST")
        
        if res.get("status") != "SUCCESS":
            error_msg = res.get("error", {}).get("message", "Unknown error")
            return False, f"❌ Gagal mengambil data: {error_msg}", []
        
        quotas = res["data"]["quotas"]
        my_packages = []
        
        for idx, quota in enumerate(quotas, 1):
            quota_code = quota["quota_code"]
            quota_name = quota["name"]
            group_name = quota.get("group_name", "N/A")
            
            # Get package details untuk family code
            family_code = "N/A"
            try:
                package_details = get_package(api_key, tokens, quota_code)
                if package_details:
                    family_code = package_details["package_family"]["package_family_code"]
            except Exception:
                pass
            
            # Parse benefits
            benefits_info = []
            benefits = quota.get("benefits", [])
            
            for benefit in benefits:
                benefit_id = benefit.get("id", "")
                name = benefit.get("name", "")
                data_type = benefit.get("data_type", "N/A")
                remaining = benefit.get("remaining", 0)
                total = benefit.get("total", 0)
                
                if data_type == "DATA":
                    remaining_str = format_quota_byte(remaining)
                    total_str = format_quota_byte(total)
                    quota_str = f"{remaining_str} / {total_str}"
                elif data_type == "VOICE":
                    quota_str = f"{remaining/60:.2f} / {total/60:.2f} menit"
                elif data_type == "TEXT":
                    quota_str = f"{remaining} / {total} SMS"
                else:
                    quota_str = f"{remaining} / {total}"
                
                benefits_info.append({
                    "id": benefit_id,
                    "name": name,
                    "type": data_type,
                    "quota": quota_str
                })
            
            # FIXED: Generate short code untuk callback
            short_code = get_short_code(quota_code)
            
            package_info = {
                "number": idx,
                "name": quota_name,
                "quota_code": quota_code,
                "short_code": short_code,  # ADDED: Short code untuk button
                "group_name": group_name,
                "family_code": family_code,
                "benefits": benefits_info,
                "product_subscription_type": quota.get("product_subscription_type", ""),
                "product_domain": quota.get("product_domain", "")
            }
            
            my_packages.append(package_info)
        
        return True, f"✅ Ditemukan {len(my_packages)} paket aktif", my_packages
        
    except Exception as e:
        return False, f"❌ Error: {str(e)}", []


def get_family_packages_data(family_code: str, is_enterprise: bool = False) -> Tuple[bool, str, List[Dict]]:
    """
    Mengambil daftar paket berdasarkan family code tanpa interaksi user
    
    Args:
        family_code: Kode family paket
        is_enterprise: Apakah enterprise package
    
    Returns:
        Tuple[bool, str, List[Dict]]: (success, message, packages_list)
    """
    try:
        api_key = AuthInstance.api_key
        tokens = AuthInstance.get_active_tokens()
        
        if not tokens:
            return False, "❌ Tidak ada akun aktif.", []
        
        # Get family data
        family_data = get_family(api_key, tokens, family_code, is_enterprise)
        
        if not family_data:
            return False, f"❌ Family code '{family_code}' tidak ditemukan.", []
        
        family_name = family_data["package_family"].get("name", "Unknown")
        package_variants = family_data.get("package_variants", [])
        
        if not package_variants:
            return False, f"❌ Tidak ada paket tersedia untuk family '{family_name}'.", []
        
        packages_list = []
        option_number = 1
        
        for variant in package_variants:
            variant_code = variant["package_variant_code"]
            variant_name = variant.get("name", "")
            package_options = variant.get("package_options", [])
            
            for option in package_options:
                option_name = option.get("name", "")
                price = option.get("price", 0)
                validity = option.get("validity", "")
                package_option_code = option["package_option_code"]
                option_order = option.get("order", 0)
                
                # FIXED: Generate short code untuk callback
                short_code = get_short_code(package_option_code)
                
                packages_list.append({
                    "number": option_number,
                    "family_name": family_name,
                    "family_code": family_code,
                    "variant_code": variant_code,
                    "variant_name": variant_name,
                    "option_name": option_name,
                    "option_code": package_option_code,
                    "short_code": short_code,  # ADDED: Short code untuk button
                    "option_order": option_order,
                    "price": price,
                    "validity": validity
                })
                
                option_number += 1
        
        return True, f"✅ Ditemukan {len(packages_list)} paket di family '{family_name}'", packages_list
        
    except Exception as e:
        return False, f"❌ Error: {str(e)}", []


def get_package_detail_data(package_option_code: str, is_enterprise: bool = False) -> Tuple[bool, str, Optional[Dict]]:
    """
    Mengambil detail paket berdasarkan option code
    
    Args:
        package_option_code: Kode opsi paket (bisa short code atau full code)
        is_enterprise: Apakah enterprise package
    
    Returns:
        Tuple[bool, str, Optional[Dict]]: (success, message, package_detail)
    """
    try:
        api_key = AuthInstance.api_key
        tokens = AuthInstance.get_active_tokens()
        
        if not tokens:
            return False, "❌ Tidak ada akun aktif.", None
        
        # FIXED: Check if it's short code, convert to full code
        if len(package_option_code) == 16 and package_option_code in CODE_MAPPING:
            package_option_code = CODE_MAPPING[package_option_code]
        
        package = get_package(api_key, tokens, package_option_code)
        
        if not package:
            return False, f"❌ Paket dengan kode '{package_option_code}' tidak ditemukan.", None
        
        # Extract package info
        family_name = package.get("package_family", {}).get("name", "")
        variant_name = package.get("package_detail_variant", {}).get("name", "")
        option_name = package.get("package_option", {}).get("name", "")
        price = package["package_option"]["price"]
        validity = package["package_option"]["validity"]
        payment_for = package["package_family"]["payment_for"]
        family_code = package.get("package_family", {}).get("package_family_code", "")
        plan_type = package["package_family"]["plan_type"]
        point = package["package_option"]["point"]
        
        # Parse benefits
        benefits_info = []
        benefits = package["package_option"].get("benefits", [])
        
        for benefit in benefits:
            benefit_name = benefit.get("name", "")
            item_id = benefit.get("item_id", "")
            data_type = benefit.get("data_type", "")
            total = benefit.get("total", 0)
            is_unlimited = benefit.get("is_unlimited", False)
            
            quota_str = ""
            if data_type == "VOICE" and total > 0:
                quota_str = f"{total/60:.2f} menit"
            elif data_type == "TEXT" and total > 0:
                quota_str = f"{total} SMS"
            elif data_type == "DATA" and total > 0:
                quota_str = format_quota_byte(int(total))
            elif total > 0:
                quota_str = f"{total} ({data_type})"
            
            benefits_info.append({
                "name": benefit_name,
                "item_id": item_id,
                "type": data_type,
                "quota": quota_str,
                "is_unlimited": is_unlimited
            })
        
        # Get addons
        addons_data = []
        try:
            addons = get_addons(api_key, tokens, package_option_code)
            if addons:
                bonuses = addons.get("bonuses", [])
                for bonus in bonuses:
                    addons_data.append({
                        "name": bonus.get("name", ""),
                        "code": bonus.get("package_option_code", "")
                    })
        except Exception:
            pass
        
        # Generate short code for this package too
        short_code = get_short_code(package_option_code)
        
        package_detail = {
            "title": f"{family_name} - {variant_name} - {option_name}".strip(),
            "family_name": family_name,
            "variant_name": variant_name,
            "option_name": option_name,
            "family_code": family_code,
            "option_code": package_option_code,
            "short_code": short_code,  # ADDED
            "price": price,
            "validity": validity,
            "payment_for": payment_for,
            "plan_type": plan_type,
            "point": point,
            "benefits": benefits_info,
            "addons": addons_data
        }
        
        return True, "✅ Detail paket berhasil diambil", package_detail
        
    except Exception as e:
        return False, f"❌ Error: {str(e)}", None


def format_package_list_message(packages: List[Dict]) -> str:
    """Format daftar paket menjadi pesan Telegram dengan HTML formatting"""
    if not packages:
        return "Tidak ada paket ditemukan."
    
    message = ""
    for pkg in packages:
        message += f"\n<b>{pkg['number']}. {pkg['option_name']}</b>\n"
        if pkg.get('variant_name'):
            message += f"   📦 Variant: {pkg['variant_name']}\n"
        message += f"   💰 Harga: Rp {pkg['price']:,}\n"
        if pkg.get('validity'):
            message += f"   ⏰ Masa Aktif: {pkg['validity']}\n"
        # Don't show full code in message, too long
        message += "   " + "─" * 40 + "\n"
    
    return message


def format_my_packages_message(packages: List[Dict]) -> str:
    """Format my packages menjadi pesan Telegram dengan HTML formatting"""
    if not packages:
        return "Tidak ada paket aktif."
    
    message = ""
    for pkg in packages:
        message += f"\n<b>{pkg['number']}. {pkg['name']}</b>\n"
        message += f"   📦 Group: {pkg['group_name']}\n"
        
        if pkg['benefits']:
            message += "   📊 Benefits:\n"
            for benefit in pkg['benefits']:
                message += f"      • {benefit['name']}\n"
                message += f"        {benefit['type']}: {benefit['quota']}\n"
        
        message += "   " + "─" * 40 + "\n"
    
    return message


def format_package_detail_message(detail: Dict) -> str:
    """Format package detail menjadi pesan Telegram dengan HTML formatting"""
    message = f"<b>📦 {detail['title']}</b>\n\n"
    message += f"💰 Harga: <b>Rp {detail['price']:,}</b>\n"
    message += f"⏰ Masa Aktif: {detail['validity']}\n"
    message += f"🎯 Plan Type: {detail['plan_type']}\n"
    message += f"⭐ Point: {detail['point']}\n"
    message += f"💳 Payment For: {detail['payment_for']}\n"
    message += f"👨‍👩‍👧 Family Code: <code>{detail['family_code']}</code>\n"
    message += "\n"
    
    if detail['benefits']:
        message += "<b>📊 Benefits:</b>\n"
        for benefit in detail['benefits']:
            message += f"  • {benefit['name']}\n"
            message += f"    Type: {benefit['type']}\n"
            if benefit['quota']:
                message += f"    Quota: {benefit['quota']}\n"
            if benefit['is_unlimited']:
                message += "    ✨ Unlimited\n"
        message += "\n"
    
    if detail['addons']:
        message += "<b>🎁 Addons/Bonuses:</b>\n"
        for addon in detail['addons']:
            message += f"  • {addon['name']}\n"
    
    return message
