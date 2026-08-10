# -*- coding: utf8 -*-
"""
优雅版 mimotion：每天固定时刻（北京时间 12:30，由 GitHub Actions cron 触发）刷一次随机步数。

- GitHub Actions 每天 12:30(北京) 触发一次本脚本，脚本对所有账号各刷一次随机步数。
- 手动触发 workflow 并勾选 force 时同样刷全部账号（补刷/测试用）。
- 登录沿用华米三层令牌链，token 用 AES_KEY 加密缓存在 encrypted_tokens.data。
- 刷完后通过 Telegram 推送结果。
"""
import json
import os
import random
import time
import traceback
import uuid
from datetime import datetime

import pytz

from util.aes_help import encrypt_data, decrypt_data
import util.zepp_helper as zepp_helper
from util.push_util import send_telegram_message

BJ_TZ = pytz.timezone("Asia/Shanghai")


# ---------------------------------------------------------------- 时间工具

def bj_now():
    """当前北京时间 datetime"""
    return datetime.now().astimezone(BJ_TZ)


def format_now():
    return bj_now().strftime("%Y-%m-%d %H:%M:%S")


def get_time():
    """毫秒时间戳字符串"""
    return "%.0f" % (bj_now().timestamp() * 1000)


# ---------------------------------------------------------------- 配置

def get_int_default(config, key, default):
    try:
        return int(config.get(key) or default)
    except (TypeError, ValueError):
        return int(default)


def normalize_user(user: str) -> str:
    """与 Zepp App 一致：手机号补 +86 前缀，邮箱保持不变。"""
    user = user.strip()
    if user.startswith("+86") or "@" in user:
        return user
    return "+86" + user


class Config:
    def __init__(self, raw: dict):
        self.user_list = [normalize_user(u) for u in (raw.get("USER") or "").split("#") if u.strip()]
        self.pwd_list = [p.strip() for p in (raw.get("PWD") or "").split("#") if p.strip()]
        self.min_step = get_int_default(raw, "MIN_STEP", 18000)
        self.max_step = get_int_default(raw, "MAX_STEP", 25000)
        self.sleep_gap = get_int_default(raw, "SLEEP_GAP", 5)
        self.tg_bot_token = (raw.get("TELEGRAM_BOT_TOKEN") or "").strip()
        self.tg_chat_id = (raw.get("TELEGRAM_CHAT_ID") or "").strip()

    @property
    def valid(self):
        return (self.user_list and len(self.user_list) == len(self.pwd_list)
                and self.max_step >= self.min_step)


# ---------------------------------------------------------------- 登录与刷步

def desensitize(user: str):
    """账号脱敏，避免公开日志泄露全账号。"""
    if len(user) <= 8:
        n = max(len(user) // 3, 1)
        return f"{user[:n]}***{user[-n:]}"
    return f"{user[:3]}****{user[-4:]}"


class MiMotionRunner:
    def __init__(self, user, password, user_tokens: dict):
        self.user = user  # 已归一化(+86 前缀或邮箱)
        self.is_phone = user.startswith("+86")
        self.password = password
        self.user_tokens = user_tokens
        self.logs = []

    def log(self, msg):
        self.logs.append(msg)

    def _load_token_cache(self):
        info = self.user_tokens.get(self.user)
        if not info:
            return None
        device_id = info.get("device_id") or str(uuid.uuid4())
        info["device_id"] = device_id
        return info

    def login(self) -> str | None:
        """获取 app_token，返回 None 表示失败。优先用缓存，逐级失效回退。"""
        info = self._load_token_cache()
        if info is not None:
            app_token = info.get("app_token")
            if app_token:
                ok, _msg = zepp_helper.check_app_token(app_token)
                if ok:
                    self.log("使用加密保存的 app_token")
                    return app_token
                self.log("app_token 失效，尝试用 login_token 换新")
                app_token, _msg = zepp_helper.grant_app_token(info.get("login_token"))
                if app_token:
                    info["app_token"] = app_token
                    info["app_token_time"] = get_time()
                    return app_token
                self.log("login_token 失效，重新登录")
                access_token, _msg = zepp_helper.login_access_token(self.user, self.password)
            else:
                self.log("无 app_token，重新登录")
                access_token, _msg = zepp_helper.login_access_token(self.user, self.password)
        else:
            access_token, _msg = zepp_helper.login_access_token(self.user, self.password)

        if access_token is None:
            self.log(f"登录失败：{_msg}")
            return None

        device_id = info["device_id"] if info else str(uuid.uuid4())
        login_token, app_token, user_id, msg = zepp_helper.grant_login_tokens(
            access_token, device_id, self.is_phone)
        if login_token is None:
            self.log(f"登录换取令牌失败：{msg}")
            return None
        info = info or {}
        info.update({
            "access_token": access_token,
            "login_token": login_token,
            "app_token": app_token,
            "user_id": user_id,
            "device_id": device_id,
            "access_token_time": get_time(),
            "login_token_time": get_time(),
            "app_token_time": get_time(),
        })
        self.user_tokens[self.user] = info
        return app_token

    def brush(self, step: int) -> tuple[bool, str]:
        """刷步。返回 (成功, 消息)。"""
        app_token = self.login()
        if app_token is None:
            return False, "登陆失败"
        user_id = self.user_tokens[self.user].get("user_id")
        ok, msg = zepp_helper.post_fake_brand_data(str(step), app_token, user_id)
        return ok, msg


# ---------------------------------------------------------------- token 持久化

def prepare_user_tokens(aes_key: bytes) -> dict:
    path = "encrypted_tokens.data"
    if os.path.exists(path):
        with open(path, "rb") as f:
            data = f.read()
        try:
            return json.loads(decrypt_data(data, aes_key, None).decode("utf-8"))
        except Exception:
            print("密钥不正确或者加密内容损坏，放弃缓存 token")
    return dict()


def persist_user_tokens(user_tokens: dict, aes_key: bytes):
    path = "encrypted_tokens.data"
    origin = json.dumps(user_tokens, ensure_ascii=False).encode("utf-8")
    with open(path, "wb") as f:
        f.write(encrypt_data(origin, aes_key, None))


# ---------------------------------------------------------------- 主流程

def main():
    config_json = os.environ.get("CONFIG")
    if not config_json:
        print("未配置 CONFIG 变量，无法执行")
        exit(1)
    try:
        config = Config(json.loads(config_json))
    except json.JSONDecodeError:
        print("CONFIG 不是合法 JSON，请检查格式（双引号、无多余逗号）")
        traceback.print_exc()
        exit(1)
    if not config.valid:
        print("CONFIG 校验失败：USER/PWD 用 # 分隔且数量一致，MAX_STEP>=MIN_STEP")
        exit(1)

    force = os.environ.get("FORCE", "").lower() in ("1", "true", "yes")
    if force:
        print(f"[{format_now()}] 手动强制刷全部账号")

    aes_key = None
    raw_key = os.environ.get("AES_KEY")
    if raw_key:
        raw_key = raw_key.encode("utf-8")
        if len(raw_key) == 16:
            aes_key = raw_key
        else:
            print("AES_KEY 长度必须为 16 字符，本次不缓存 token")
    user_tokens = prepare_user_tokens(aes_key) if aes_key else dict()

    results = []
    total = len(config.user_list)
    for idx, user in enumerate(config.user_list):
        step = random.randint(config.min_step, config.max_step)
        runner = MiMotionRunner(user, config.pwd_list[idx], user_tokens)
        try:
            ok, msg = runner.brush(step)
            exec_msg = f"修改步数({step})[{msg}]"
        except Exception as e:
            ok, exec_msg = False, f"执行异常:{e}\n{traceback.format_exc()}"
        for line in runner.logs:
            print(f"[{desensitize(user)}] {line}")
        print(f"[{format_now()}] {desensitize(user)} -> {exec_msg}")
        results.append({"user": user, "success": ok, "msg": exec_msg})
        if idx < total - 1:
            time.sleep(config.sleep_gap)

    success = sum(1 for r in results if r["success"])
    summary = f"刷步完成，共{len(results)}个账号，成功{success}，失败{len(results) - success}"
    lines = [summary, ""]
    for r in results:
        mark = "✅" if r["success"] else "❌"
        lines.append(f"{mark} {r['user']}：{r['msg']}")
    print("\n".join(lines))

    if config.tg_bot_token and config.tg_chat_id:
        send_telegram_message(config.tg_bot_token, config.tg_chat_id, "\n".join(lines))
    else:
        print("未配置 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID，跳过推送")

    if aes_key:
        persist_user_tokens(user_tokens, aes_key)


if __name__ == "__main__":
    main()
