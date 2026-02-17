from app.client.ciam import get_otp, submit_otp
from app.menus.util import clear_screen, pause
from app.service.auth import AuthInstance


def login_prompt(api_key: str):
    clear_screen()
    print("-------------------------------------------------------")
    print("Login ke MyXL")
    print("-------------------------------------------------------")

    phone_number = input("Masukan nomor XL (628xxxx): ").strip()

    if not phone_number.startswith("628") or not (10 <= len(phone_number) <= 14):
        print("Nomor tidak valid")
        pause()
        return None, None

    subscriber_id = get_otp(phone_number)
    if not subscriber_id:
        print("Gagal request OTP")
        pause()
        return None, None

    print("OTP berhasil dikirim")

    for attempt in range(5, 0, -1):
        print(f"Sisa percobaan: {attempt}")
        otp = input("Masukkan OTP: ").strip()

        tokens = submit_otp(api_key, "SMS", phone_number, otp)
        if tokens:
            print("Login berhasil")
            return phone_number, tokens["refresh_token"]

        print("OTP salah")

    print("Gagal login")
    pause()
    return None, None


def show_account_menu():
    clear_screen()
    AuthInstance.load_tokens()

    users = AuthInstance.refresh_tokens
    active_user = AuthInstance.get_active_user()

    while True:
        clear_screen()

        if active_user is None:
            number, refresh_token = login_prompt(AuthInstance.api_key)
            if not refresh_token:
                continue

            AuthInstance.add_refresh_token(int(number), refresh_token)
            AuthInstance.load_tokens()
            active_user = AuthInstance.get_active_user()
            continue

        print("Akun tersimpan:")
        for idx, user in enumerate(users):
            marker = "✅" if active_user and user["number"] == active_user["number"] else ""
            print(f"{idx+1}. {user['number']} {marker}")

        print("0. Tambah akun")
        print("00. Kembali")

        choice = input("Pilih: ").strip()

        if choice == "00":
            return active_user["number"]

        if choice == "0":
            active_user = None
            continue

        if choice.isdigit() and 1 <= int(choice) <= len(users):
            return users[int(choice)-1]["number"]

        pause()
