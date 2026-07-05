"""POST /api/pivot — 透视表查询

接收 PivotConfig JSON，返回聚合数据 + Vega-Lite 图表规格。
支持 LRU 缓存（TTL 5 分钟）。
"""

from __future__ import annotations

import hashlib
import json
import logging
import time

from fastapi import APIRouter, HTTPException

from core.pivot_sql_builder import execute_pivot
from models import PivotConfig, PivotResponse

logger = logging.getLogger("api_pivot")

router = APIRouter(prefix="/api", tags=["pivot"])

# 简单 TTL 缓存
_cache: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 300  # 5 分钟
_CACHE_MAXSIZE = 128


def _config_hash(config: PivotConfig) -> str:
    """生成配置的哈希值作为缓存键"""
    raw = config.model_dump_json()
    return hashlib.md5(raw.encode()).hexdigest()


def _get_cached(hash_key: str) -> dict | None:
    """从缓存读取，过期返回 None"""
    entry = _cache.get(hash_key)
    if entry is None:
        return None
    ts, result = entry
    if time.time() - ts > _CACHE_TTL:
        del _cache[hash_key]
        return None
    return result


def _set_cached(hash_key: str, result: dict) -> None:
    """写入缓存，超限时淘汰最旧的"""
    if len(_cache) >= _CACHE_MAXSIZE:
        # 淘汰最旧的一个
        oldest_key = min(_cache.keys(), key=lambda k: _cache[k][0])
        del _cache[oldest_key]
    _cache[hash_key] = (time.time(), result)


@router.post("/pivot", response_model=PivotResponse)
async def pivot_query(config: PivotConfig):
    """执行表查询"""
    hash_key = _config_hash(config)

    # 检查缓存
    cached = _get_cached(hash_key)
    if cached is not None:
        logger.debug("缓存命中")
        return PivotResponse(**cached)

    try:
        result = execute_pivot(config)
        _set_cached(hash_key, result)
        return PivotResponse(**result)
    except Exception as e:
        logger.error("报表查询失败: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
