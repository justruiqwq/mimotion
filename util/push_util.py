# -*- coding: utf8 -*-
"""推送工具：仅保留 Telegram Bot 推送。"""
import json

import requests


def send_telegram_message(bot_token: str, chat_id: str, text: str):
    """通过 Telegram Bot API 发送消息，失败仅打印日志不影响主流程。"""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code == 200:
            result = resp.json()
            if result.get("ok"):
                print("Telegram 推送成功")
            else:
                print(f"Telegram 推送失败: {json.dumps(result, ensure_ascii=False)}")
        else:
            print(f"Telegram 推送失败: HTTP {resp.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Telegram 推送网络异常: {e}")
