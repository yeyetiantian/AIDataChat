"""FastAPI 应用入口

包含：
1. CORS 配置（允许前端跨域访问）
2. 路由注册

原始表查询（6 表 LEFT JOIN），无需初始化宽表。
或通过 API: POST /api/admin/refresh_wide_detail
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# 加载 .env 配置
load_dotenv()

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    from core.chat_db import init_db
    init_db()
    logger.info("=" * 60)
    logger.info("企业级数据透视分析系统 启动中...")
    logger.info("环境: %s", os.getenv("ENV", "development"))
    logger.info("=" * 60)
    yield
    logger.info("应用关闭")


app = FastAPI(
    title="企业级数据透视分析系统",
    description="基于 DuckDB + Vega-Lite 的 Web 数据透视分析系统",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins="*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
from routers.api_chat import router as chat_router
from routers.api_admin import router as admin_router
from routers.api_charts import router as charts_router
from routers.api_recommend import router as recommend_router
from routers.api_auth import router as auth_router
from routers.api_sessions import router as sessions_router
from routers.api_boards import router as boards_router
from routers.api_monitor import router as monitor_router
from routers.api_functions import router as functions_router
from routers.api_dtc_query import router as dtc_query_router
app.include_router(chat_router)
app.include_router(functions_router)
app.include_router(admin_router)
app.include_router(charts_router)
app.include_router(recommend_router)
app.include_router(auth_router)
app.include_router(sessions_router)
app.include_router(boards_router)
app.include_router(monitor_router)
app.include_router(dtc_query_router)
# 生产环境：挂载前端静态文件
if getattr(sys, "frozen", False):
    _dist_dir = os.path.join(os.path.dirname(sys.executable), "dist")
else:
    _dist_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")

if os.path.isdir(_dist_dir):
    logger.info("挂载前端静态文件: %s", _dist_dir)
    app.mount("/", StaticFiles(directory=_dist_dir, html=True), name="frontend")
else:
    logger.warning("前端构建目录不存在（开发模式无需担心）: %s", _dist_dir)


@app.get("/")
async def root():
    return {
        "service": "企业级数据透视分析系统",
        "version": "1.0.0",
        "docs": "/docs",
        "api": {
            "chat": "POST /api/chat — AI 对话分析",
            "charts": "GET/POST /api/charts — 看板管理",
            "boards": "GET/POST /api/boards — 多看板管理",
            "recommend": "POST /api/recommend-chart — 图表类型推荐",
            "admin": {
                "refresh": "POST /api/admin/refresh — 重建",
                "health": "GET /api/admin/health — 健康检查",
            },
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
