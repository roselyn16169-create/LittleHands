"""LittleHands 小手家务 —— FastAPI 入口。

启动方式（在 backend/ 目录下）：
    ../.venv/bin/uvicorn main:app --reload --port 8000
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from database import db, init_db
from routers import admin, records, tasks

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """服务启动时自动建库建表 + 种子数据（幂等）。"""
    init_db()
    yield


app = FastAPI(
    title="LittleHands 小手家务 API",
    version="1.1.0",
    description="儿童家务打卡 / 小金库 / 家长管理后台",
    lifespan=lifespan,
)

@app.middleware("http")
async def no_cache_static(request, call_next):
    """静态资源（页面/JS/CSS）一律 no-cache：浏览器每次协商校验，改版立即生效，杜绝旧缓存捣乱。"""
    resp = await call_next(request)
    p = request.url.path
    if p.startswith("/js/") or p.startswith("/css/") or p.endswith(".html") or p == "/":
        resp.headers["Cache-Control"] = "no-cache"
    return resp


# ---- 业务路由 ----
app.include_router(tasks.router)      # 儿童端：家务列表
app.include_router(records.router)    # 儿童端：打卡/明细/历史/汇总
app.include_router(admin.router)      # 家长端：鉴权/任务 CRUD/日志/统计


@app.get("/api/health", tags=["系统"])
def health():
    """健康检查。"""
    with db() as conn:
        task_count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    return {"status": "ok", "tasks": task_count}


# 注意：静态目录挂载必须放在最后，避免吞掉 /api/* 路由
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
