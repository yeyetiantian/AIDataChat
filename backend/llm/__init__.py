"""Private LLM OAuth2 认证客户端

对接企业内部私有 LLM，使用 client_credentials 模式获取 token 后调用 OpenAI 兼容接口。
"""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

import requests

logger = logging.getLogger("private_llm")

_TOKEN_CACHE: dict[str, any] = {"token": None, "expires_at": 0.0}


def get_token() -> str:
    """获取访问令牌（带缓存刷新）"""
    now = time.time()
    if _TOKEN_CACHE["token"] and now < _TOKEN_CACHE["expires_at"]:
        return _TOKEN_CACHE["token"]

    client_id = os.getenv("PRIVATE_LLM_CLIENT_ID")
    client_secret = os.getenv("PRIVATE_LLM_CLIENT_SECRET")
    token_url = os.getenv("PRIVATE_LLM_TOKEN_URL")

    if not all([client_id, client_secret, token_url]):
        raise ValueError("PRIVATE_LLM_CLIENT_ID / PRIVATE_LLM_CLIENT_SECRET / PRIVATE_LLM_TOKEN_URL 未配置")

    headers = {
        "content-type": "application/x-www-form-urlencoded",
        "Connection": "close",
    }
    data = {
        "scope": "ALL",
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }

    logger.info("正在获取 LLM token: %s", token_url)
    resp = requests.post(token_url, data=data, headers=headers, timeout=15)
    if resp.status_code != 200:
        raise RuntimeError(f"获取 token 失败 ({resp.status_code}): {resp.text}")

    body = resp.json()
    token = body.get("access_token")
    if not token:
        raise RuntimeError(f"响应中无 access_token: {body}")

    # 默认 1 小时过期，提前 5 分钟刷新
    expires_in = body.get("expires_in", 3600) - 300
    _TOKEN_CACHE["token"] = token
    _TOKEN_CACHE["expires_at"] = now + max(expires_in, 60)

    logger.info("LLM token 获取成功，有效期 %ds", expires_in)
    return token


def get_auth_headers() -> dict[str, str]:
    """获取认证请求头（含 client_id，部分私有 LLM 需要在请求中传入）"""
    token = get_token()
    api_key = os.getenv("PRIVATE_LLM_API_KEY")
    return {
        "X-API-KEY": api_key,
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
    }
