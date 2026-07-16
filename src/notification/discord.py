import requests


def send_discord(webhook_url: str, message: str):
    if not webhook_url:
        return
    try:
        requests.post(webhook_url, json={"content": message}, timeout=5)
    except Exception:
        pass
