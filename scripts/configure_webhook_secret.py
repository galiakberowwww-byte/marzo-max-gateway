import os
import secrets
import winreg


def main() -> None:
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
        try:
            existing, _ = winreg.QueryValueEx(key, "MAX_WEBHOOK_SECRET")
        except FileNotFoundError:
            existing = ""
        if existing:
            print("MAX_WEBHOOK_SECRET: already configured")
            return

        secret = secrets.token_urlsafe(32)
        winreg.SetValueEx(key, "MAX_WEBHOOK_SECRET", 0, winreg.REG_SZ, secret)
    print("MAX_WEBHOOK_SECRET: configured")


if __name__ == "__main__":
    main()
