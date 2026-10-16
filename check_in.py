#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GLaDOS 自动签到。

2026-09 起 GLaDOS 变更了签到认证，需要同时满足两点：
1. Cookie 必须是完整会话（新增 gld:sess / gld:sess.sig），只带旧的 koa:sess 会返回 code -2「没有权限」。
2. 请求的 User-Agent 必须与取得该 Cookie 的浏览器一致，否则签到返回 code 4 / device-mismatch。

环境变量：
- GLADOS_COOKIE：浏览器完整 Cookie。多个账号用 && 分隔。
- GLADOS_UA：取 Cookie 的浏览器 User-Agent（浏览器控制台执行 navigator.userAgent 复制）。
- GLADOS_ORIGIN：API 站点根地址，默认 https://glados.rocks。
- GLADOS_TOKEN：签到 token，默认取站点域名。
"""

from __future__ import annotations

import json
import math
import os
import sys
from typing import Any
from urllib.parse import urlparse

import requests

DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
)

HINT_COOKIE = (
    "Cookie 已失效或格式过旧。请重新登录站点，复制完整 Cookie（需含 gld:sess 与 gld:sess.sig 两段）"
    "更新 Secret GLADOS_COOKIE。"
)
HINT_UA = (
    "浏览器身份校验失败。请在取 Cookie 的那个浏览器的控制台执行 navigator.userAgent，"
    "把结果原样填到变量 GLADOS_UA（Cookie 与 UA 必须来自同一浏览器）。"
)


def parse_cookie(cookie_raw: str) -> dict[str, str]:
    raw = cookie_raw.strip()
    if raw.lower().startswith("cookie:"):
        raw = raw.split(":", 1)[1].strip()
    if raw.startswith("["):
        items = json.loads(raw)
        return {
            str(item["name"]): str(item["value"])
            for item in items
            if isinstance(item, dict) and item.get("name")
        }

    out: dict[str, str] = {}
    for part in raw.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, value = part.split("=", 1)
        out[name.strip()] = value.strip()
    return out


def resp_json(resp: requests.Response) -> dict[str, Any]:
    encoding = requests.utils.guess_json_utf(resp.content)
    if encoding:
        try:
            return json.loads(resp.content.decode(encoding))
        except UnicodeDecodeError:
            pass
    return json.loads(resp.text)


def env_first(*names: str) -> str:
    for name in names:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return ""


def glados_origin() -> str:
    return (env_first("GLADOS_ORIGIN") or "https://glados.rocks").rstrip("/")


def glados_ua() -> str:
    return env_first("GLADOS_UA", "GLADOS_USER_AGENT", "GLADOS_USERAGENT") or DEFAULT_UA


def glados_token(origin: str) -> str:
    return env_first("GLADOS_TOKEN") or (urlparse(origin).hostname or origin)


def convert_traffic_size(size_bytes: int) -> str:
    if size_bytes <= 0:
        return "0B"
    names = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {names[i]}"


def interpret_checkin(data: dict[str, Any]) -> tuple[bool, str, str]:
    """返回 (是否成功, 展示信息, 附加提示)。"""
    code = data.get("code")
    message = str(data.get("message") or data)
    reason = str(data.get("reason") or "")

    if code == 0:
        return True, f"签到成功（{message}）", ""
    if code == 1:
        return True, f"今日已签到（{message}）", ""
    if reason == "device-mismatch":
        devices = ""
        if data.get("loginDevice") or data.get("currentDevice"):
            devices = (
                f"（登录设备: {data.get('loginDevice') or '-'}"
                f" / 本次请求: {data.get('currentDevice') or '-'}）"
            )
        return False, f"设备不一致{devices}：{message}", HINT_UA
    if "没有权限" in message or str(code) == "-2":
        return False, message, HINT_COOKIE
    if "utomated check-in" in message or reason:
        return False, f"请求被拒绝（{reason or message}）", HINT_UA
    return False, f"未知响应（code={code}）：{message}", ""


def check_in_one(cookie_raw: str, origin: str, ua: str, token: str) -> int:
    cookie_raw = cookie_raw.strip()
    if not cookie_raw:
        return 0

    cookies = parse_cookie(cookie_raw)
    if not cookies:
        print("[错误] Cookie 解析为空，请检查 GLADOS_COOKIE 是否填写完整。", flush=True)
        return 1
    if not any(name.startswith("gld:") for name in cookies):
        print(
            "[警告] Cookie 缺少 gld:sess 段，2026-09 改版后旧格式会返回「没有权限」，"
            "建议重新登录后复制完整 Cookie。",
            flush=True,
        )

    headers = {
        "User-Agent": ua,
        "Origin": origin,
        "Referer": f"{origin}/console/checkin",
        "Accept": "application/json, text/plain, */*",
    }

    r_check = requests.post(
        f"{origin}/api/user/checkin",
        json={"token": token},
        headers=headers,
        cookies=cookies,
        timeout=30,
    )
    r_check.raise_for_status()
    check_data = resp_json(r_check)
    ok, detail, hint = interpret_checkin(check_data)

    print(f"签到: {detail}", flush=True)
    print(f"原始签到响应: {json.dumps(check_data, ensure_ascii=False)}", flush=True)
    if hint:
        print(f"[提示] {hint}", flush=True)

    r_status = requests.get(
        f"{origin}/api/user/status",
        headers=headers,
        cookies=cookies,
        timeout=30,
    )
    r_status.raise_for_status()
    status = resp_json(r_status)
    if status.get("code") != 0:
        print(f"[错误] 获取账号状态失败: {json.dumps(status, ensure_ascii=False)}", flush=True)
        if not ok:
            print(f"[提示] {HINT_COOKIE}", flush=True)
        return 1

    data = status.get("data") or {}
    print(f"账号: {data.get('email')}", flush=True)
    print(f"剩余天数: {data.get('leftDays')}", flush=True)
    print(f"流量: {convert_traffic_size(int(float(data.get('traffic') or 0)))}", flush=True)
    print(f"已用天数: {data.get('days')}", flush=True)
    return 0 if ok else 1


def main() -> int:
    raw = (os.environ.get("GLADOS_COOKIE") or "").strip()
    if not raw:
        print("请设置环境变量 GLADOS_COOKIE（完整 Cookie 字符串）。", flush=True)
        return 1

    origin = glados_origin()
    ua = glados_ua()
    token = glados_token(origin)
    print(f"使用站点: {origin}", flush=True)
    print(f"签到 token: {token}", flush=True)
    print(f"User-Agent: {ua}", flush=True)
    if not env_first("GLADOS_UA", "GLADOS_USER_AGENT", "GLADOS_USERAGENT"):
        print(
            "[提示] 未设置 GLADOS_UA，将使用默认 Chrome UA；"
            "若报 device-mismatch，请填入取 Cookie 浏览器的 navigator.userAgent。",
            flush=True,
        )

    parts = [p.strip() for p in raw.split("&&") if p.strip()]
    exit_code = 0
    for i, ck in enumerate(parts):
        if len(parts) > 1:
            print(f"--- 账号 {i + 1}/{len(parts)} ---", flush=True)
        try:
            exit_code |= check_in_one(ck, origin, ua, token)
        except requests.RequestException as e:
            print(f"[请求失败] {e}", flush=True)
            exit_code = 1
        except (KeyError, TypeError, ValueError) as e:
            print(f"[解析失败] {e}", flush=True)
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
