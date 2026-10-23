"""SQLite 数据库：连接管理、建表与种子数据初始化。"""
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from models import DDL_SQL, SEED_SETTINGS, SEED_TASKS
from utils import now_iso

# 目录定位：backend/database.py 的上一级即项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
# 环境变量 CHORE_DB 可指向独立数据库文件（测试/演示时避免污染开发库）
DB_PATH = Path(os.environ.get("CHORE_DB", DATA_DIR / "chore.db"))


def get_conn() -> sqlite3.Connection:
    """返回一个新连接。

    SQLite 本地连接开销极小，采用「每次请求独立连接」的简单策略，
    天然线程安全（FastAPI 同步端点运行在线程池中），无需连接池。
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # 支持按字段名取值：row["name"]
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db():
    """事务上下文：自动 commit / rollback / close，供路由端点使用。"""
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """建表 + 写入种子数据（幂等：已有数据不会重复插入）。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_conn()
    try:
        conn.executescript(DDL_SQL)
        _seed_settings(conn)
        _seed_tasks(conn)
        conn.commit()
    finally:
        conn.close()


def _seed_settings(conn: sqlite3.Connection) -> None:
    for key, value in SEED_SETTINGS.items():
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )


def _seed_tasks(conn: sqlite3.Connection) -> None:
    """仅在空表时插入种子家务，绝不覆盖家长后续的修改。"""
    if conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]:
        return
    now = now_iso()
    for sort_no, t in enumerate(SEED_TASKS, start=1):
        conn.execute(
            """INSERT INTO tasks
               (name, pinyin, icon, price, daily_limit, sort_order, is_active, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)""",
            (t["name"], t["pinyin"], t["icon"], t["price"],
             t.get("daily_limit"), sort_no, now, now),
        )
