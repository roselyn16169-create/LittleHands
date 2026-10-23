"""儿童端：家务列表（打卡页卡片数据）。"""
from fastapi import APIRouter

from database import db
from utils import to_yuan, today_str

router = APIRouter(prefix="/api/tasks", tags=["儿童端 · 家务列表"])


@router.get("")
def list_tasks():
    """上架中的家务，附「今日已打卡次数 / 今日剩余次数」，前端据此置灰超额卡片。"""
    today = today_str()
    with db() as conn:
        tasks = conn.execute(
            """SELECT id, name, pinyin, icon, price, daily_limit
               FROM tasks WHERE is_active = 1
               ORDER BY sort_order, id"""
        ).fetchall()
        done_rows = conn.execute(
            """SELECT task_id, COALESCE(SUM(quantity), 0) AS done
               FROM daily_records WHERE record_date = ?
               GROUP BY task_id""",
            (today,),
        ).fetchall()
    done_map = {r["task_id"]: r["done"] for r in done_rows}

    return {"tasks": [
        {
            "id": t["id"],
            "name": t["name"],
            "pinyin": t["pinyin"],
            "icon": t["icon"],
            "price": to_yuan(t["price"]),          # 元
            "daily_limit": t["daily_limit"],
            "done_today": done_map.get(t["id"], 0),
            "remain_today": None if t["daily_limit"] is None
                           else max(t["daily_limit"] - done_map.get(t["id"], 0), 0),
        }
        for t in tasks
    ]}
