#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GLaDOS 自动签到。

环境变量：
- GLADOS_COOKIE：浏览器完整 Cookie（含 koa:sess 与 koa:sess.sig）。
- GLADOS_ORIGIN：API 站点根地址，默认 https://glados.rocks；若 Cookie 在 glados.space 下且签到失败，设为 https://glados.space。
"""

from __future__ import annotations

import json
import math
import os
import sys
from typing import Any

import requests

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def parse_cookie_string(cookie_str: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in cookie_str.strip().split(";"):
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


def glados_origin() -> str:
    raw = (os.environ.get("GLADOS_ORIGIN") or "").strip()
    if not raw:
        raw = "https://glados.rocks"
    return raw.rstrip("/")


def convert_traffic_size(size_bytes: int) -> str:
    if size_bytes <= 0:
        return "0B"
    names = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {names[i]}"


def check_in_one(cookie_raw: str, origin: str) -> int:
    cookie_raw = cookie_raw.strip()
    if not cookie_raw:
        return 0

    cookies = parse_cookie_string(cookie_raw)
    headers = {
        "User-Agent": UA,
        "Origin": origin,
        "Referer": f"{origin}/console/checkin",
    }
    check_url = f"{origin}/api/user/checkin"
    status_url = f"{origin}/api/user/status"

    r_check = requests.post(
        check_url,
        json={"token": "glados.network"},
        headers=headers,
        cookies=cookies,
        timeout=30,
    )
    r_check.raise_for_status()
    check_data = resp_json(r_check)
    message = check_data.get("message", str(check_data))

    r_status = requests.get(
        status_url,
        headers=headers,
        cookies=cookies,
        timeout=30,
    )
    r_status.raise_for_status()
    status = resp_json(r_status)
    if status.get("code") != 0:
        print(f"[错误] 获取状态失败: {status}", flush=True)
        return 1

    data = status["data"]
    print(f"账号: {data.get('email')}", flush=True)
    print(f"剩余天数: {data.get('leftDays')}", flush=True)
    print(f"流量: {convert_traffic_size(int(data.get('traffic') or 0))}", flush=True)
    print(f"已用天数: {data.get('days')}", flush=True)
    print(f"签到: {message}", flush=True)
    return 0


def main() -> int:
    raw = os.environ.get("GLADOS_COOKIE", "").strip()
    if not raw:
        print("请设置环境变量 GLADOS_COOKIE（完整 Cookie 字符串）。", flush=True)
        return 1

    origin = glados_origin()
    print(f"使用站点: {origin}", flush=True)

    parts = [p.strip() for p in raw.split("&&") if p.strip()]
    exit_code = 0
    for i, ck in enumerate(parts):
        if len(parts) > 1:
            print(f"--- 账号 {i + 1}/{len(parts)} ---", flush=True)
        try:
            exit_code |= check_in_one(ck, origin)
        except requests.RequestException as e:
            print(f"[请求失败] {e}", flush=True)
            exit_code = 1
        except (KeyError, TypeError, ValueError) as e:
            print(f"[解析失败] {e}", flush=True)
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
