import base64
import os
import json
import uuid
import requests
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta

from app.client.encrypt import (
    java_like_timestamp,
    ts_gmt7_without_colon,
    ax_api_signature,
    load_ax_fp,
    ax_device_id
)

# ================= ENV =================

BASE_CIAM_URL = os.getenv("BASE_CIAM_URL")
BASIC_AUTH = os.getenv("BASIC_AUTH")
UA = os.getenv("UA")

if not BASE_CIAM_URL:
    raise ValueError("BASE_CIAM_URL belum diset")
if not BASIC_AUTH:
    raise ValueError("BASIC_AUTH belum diset")
if not UA:
    raise ValueError("UA belum diset")

AX_DEVICE_ID = ax_device_id()
AX_FP = load_ax_fp()

# ================= UTILS =================

def validate_contact(contact: str) -> bool:
    return contact.startswith("628") and 10 <= len(contact) <= 14


# ================= OTP =================

def get_otp(contact: str) -> str | None:
    if not validate_contact(contact):
        print("Nomor tidak valid")
        return None

    url = f"{BASE_CIAM_URL}/realms/xl-ciam/auth/otp"
    params = {
        "contact": contact,
        "contactType": "SMS",
        "alternateContact": "false"
    }

    now = datetime.now(timezone(timedelta(hours=7)))

    headers = {
        "Authorization": f"Basic {BASIC_AUTH}",
        "Ax-Device-Id": AX_DEVICE_ID,
        "Ax-Fingerprint": AX_FP,
        "Ax-Request-At": java_like_timestamp(now),
        "Ax-Request-Id": str(uuid.uuid4()),
        "Ax-Request-Device": "samsung",
        "Ax-Request-Device-Model": "SM-N935F",
        "Ax-Substype": "PREPAID",
        "User-Agent": UA,
        "Accept": "application/json",
    }

    print("Requesting OTP...")

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)

        if resp.status_code != 200:
            print("OTP gagal:", resp.status_code, resp.text)
            return None

        try:
            data = resp.json()
        except Exception:
            print("OTP response bukan JSON")
            return None

        subscriber_id = data.get("subscriber_id")
        if not subscriber_id:
            print("subscriber_id tidak ada:", data)
            return None

        return subscriber_id

    except requests.RequestException as e:
        print("Network error OTP:", e)
        return None


# ================= SUBMIT OTP =================

def submit_otp(api_key: str, contact_type: str, contact: str, code: str):
    if contact_type == "SMS":
        if not validate_contact(contact) or not code.isdigit() or len(code) != 6:
            print("OTP tidak valid")
            return None
        final_contact = contact
        final_code = code

    elif contact_type == "DEVICEID":
        final_contact = base64.b64encode(contact.encode()).decode()
        final_code = code
    else:
        print("contact_type tidak didukung")
        return None

    now = datetime.now(timezone(timedelta(hours=7)))
    ts_sign = ts_gmt7_without_colon(now)
    ts_header = ts_gmt7_without_colon(now - timedelta(minutes=5))

    signature = ax_api_signature(
        api_key,
        ts_sign,
        final_contact,
        final_code,
        contact_type
    )

    url = f"{BASE_CIAM_URL}/realms/xl-ciam/protocol/openid-connect/token"

    payload = (
        f"grant_type=password"
        f"&contactType={contact_type}"
        f"&contact={final_contact}"
        f"&code={final_code}"
        f"&scope=openid"
    )

    headers = {
        "Authorization": f"Basic {BASIC_AUTH}",
        "Ax-Api-Signature": signature,
        "Ax-Device-Id": AX_DEVICE_ID,
        "Ax-Fingerprint": AX_FP,
        "Ax-Request-At": ts_header,
        "Ax-Request-Id": str(uuid.uuid4()),
        "Ax-Request-Device": "samsung",
        "Ax-Request-Device-Model": "SM-N935F",
        "Ax-Substype": "PREPAID",
        "User-Agent": UA,
        "Content-Type": "application/x-www-form-urlencoded",
    }

    print("Submitting OTP...")

    try:
        resp = requests.post(url, headers=headers, data=payload, timeout=30)

        if resp.status_code != 200:
            print("Submit OTP gagal:", resp.status_code, resp.text)
            return None

        data = resp.json()
        if "error" in data:
            print("OTP error:", data)
            return None

        return data

    except requests.RequestException as e:
        print("Network error submit OTP:", e)
        return None


# ================= REFRESH TOKEN =================

def extend_session(subscriber_id: str) -> str | None:
    url = f"{BASE_CIAM_URL}/realms/xl-ciam/auth/extend-session"
    contact_b64 = base64.b64encode(subscriber_id.encode()).decode()

    headers = {
        "Authorization": f"Basic {BASIC_AUTH}",
        "Ax-Device-Id": AX_DEVICE_ID,
        "Ax-Fingerprint": AX_FP,
        "Ax-Request-At": java_like_timestamp(datetime.now(timezone(timedelta(hours=7)))),
        "Ax-Request-Id": str(uuid.uuid4()),
        "Ax-Request-Device": "samsung",
        "Ax-Request-Device-Model": "SM-N935F",
        "Ax-Substype": "PREPAID",
        "User-Agent": UA,
    }

    params = {
        "contact": contact_b64,
        "contactType": "DEVICEID"
    }

    resp = requests.get(url, headers=headers, params=params, timeout=30)
    if resp.status_code != 200:
        print("extend_session gagal:", resp.text)
        return None

    return resp.json().get("data", {}).get("exchange_code")


def get_new_token(api_key: str, refresh_token: str, subscriber_id: str):
    url = f"{BASE_CIAM_URL}/realms/xl-ciam/protocol/openid-connect/token"

    headers = {
        "Authorization": f"Basic {BASIC_AUTH}",
        "Ax-Device-Id": AX_DEVICE_ID,
        "Ax-Fingerprint": AX_FP,
        "Ax-Request-At": java_like_timestamp(datetime.now(timezone(timedelta(hours=7)))),
        "Ax-Request-Id": str(uuid.uuid4()),
        "Ax-Substype": "PREPAID",
        "User-Agent": UA,
        "Content-Type": "application/x-www-form-urlencoded",
    }

    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }

    resp = requests.post(url, headers=headers, data=data, timeout=30)

    if resp.status_code == 400 and "Session not active" in resp.text:
        if not subscriber_id:
            return None

        exchange_code = extend_session(subscriber_id)
        if not exchange_code:
            return None

        return submit_otp(api_key, "DEVICEID", subscriber_id, exchange_code)

    resp.raise_for_status()
    return resp.json()


# ================= AUTH CODE (PIN) =================

def get_auth_code(tokens: dict, pin: str, msisdn: str) -> str | None:
    url = f"{BASE_CIAM_URL}/ciam/auth/authorization-token/generate"

    now = datetime.now(timezone(timedelta(hours=7)))

    headers = {
        "Authorization": f"Bearer {tokens['access_token']}",
        "Ax-Device-Id": AX_DEVICE_ID,
        "Ax-Fingerprint": AX_FP,
        "Ax-Request-At": java_like_timestamp(now),
        "Ax-Request-Id": str(uuid.uuid4()),
        "Ax-Request-Device": "samsung",
        "Ax-Request-Device-Model": "SM-N935F",
        "Ax-Substype": "PREPAID",
        "User-Agent": UA,
        "Content-Type": "application/json",
    }

    payload = {
        "pin": base64.b64encode(pin.encode()).decode(),
        "transaction_type": "SHARE_BALANCE",
        "receiver_msisdn": msisdn,
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)

        if resp.status_code != 200:
            print("get_auth_code gagal:", resp.status_code, resp.text)
            return None

        data = resp.json()
        if data.get("status") != "Success":
            print("get_auth_code error:", data)
            return None

        return data.get("data", {}).get("authorization_code")

    except requests.RequestException as e:
        print("Network error get_auth_code:", e)
        return None
