"""儿童端：打卡提交、明细、按月历史、累计汇总。"""
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from database import db
from schemas import SubmitRequest
from utils import now_iso, today_str, to_yuan

router = APIRouter(prefix="/api/records", tags=["儿童端 · 打卡记录"])


# ---------- 内部工具 ----------

def _validate_date(s: str) -> str:
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return s
    except ValueError:
        raise HTTPException(status_code=400, detail=f"日期格式错误，应为 YYYY-MM-DD：{s}")


def _day_detail(conn, date_str: str) -> dict:
    """某一天明细 + 合计（today 与 ?date= 共用）。"""
    rows = conn.execute(
        """SELECT id, task_id, task_name, task_icon, price, quantity, amount, created_at
           FROM daily_records WHERE record_date = ? ORDER BY id""",
        (date_str,),
    ).fetchall()
    total = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM daily_records WHERE record_date = ?",
        (date_str,),
    ).fetchone()[0]
    return {
        "date": date_str,
        "total": to_yuan(total),
        "items": [
            {
                "id": r["id"],
                "task_id": r["task_id"],
                "name": r["task_name"],       # 快照，不受后续改名影响
                "icon": r["task_icon"],
                "price": to_yuan(r["price"]),
                "quantity": r["quantity"],
                "amount": to_yuan(r["amount"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ],
    }


# ---------- 接口 ----------

@router.get("/today")
def today_records():
    """今日明细与合计。"""
    with db() as conn:
        return _day_detail(conn, today_str())


@router.get("")
def records_by_date(date: str = Query(..., min_length=10, max_length=10)):
    """指定日期明细（如 2026-10-23）。"""
    with db() as conn:
        return _day_detail(conn, _validate_date(date))


@router.post("/submit")
def submit(req: SubmitRequest):
    """一键提交：整体校验、整体入账——任一项超额则整单拒绝，杜绝写半单。"""
    today, now = today_str(), now_iso()

    # 合并同一家务的多次勾选，如 [{id:1,q:1},{id:1,q:1}] => {1: 2}
    merged = {}
    for it in req.items:
        merged[it.task_id] = merged.get(it.task_id, 0) + it.quantity

    with db() as conn:
        # 仅拼接 '?' 占位符，无注入风险
        marks = ",".join("?" * len(merged))
        rows = conn.execute(
            f"""SELECT id, name, icon, price, daily_limit, is_active
                FROM tasks WHERE id IN ({marks})""",
            tuple(merged),
        ).fetchall()
        tasks = {r["id"]: r for r in rows}

        # ---- 阶段 1：全部校验（任一失败即 400，事务回滚，一行都不写）----
        errors = []
        for task_id, qty in sorted(merged.items()):
            t = tasks.get(task_id)
            if t is None or not t["is_active"]:
                errors.append(f"id={task_id} 的家务不存在或已下架")
                continue
            done = conn.execute(
                """SELECT COALESCE(SUM(quantity), 0) FROM daily_records
                   WHERE task_id = ? AND record_date = ?""",
                (task_id, today),
            ).fetchone()[0]
            if t["daily_limit"] is not None and done + qty > t["daily_limit"]:
                errors.append(f"「{t['name']}」今日已达上限（已完成 {done}/{t['daily_limit']} 次）")
        if errors:
            raise HTTPException(status_code=400, detail="；".join(errors))

        # ---- 阶段 2：全部写入（含名称/图标/单价快照）----
        added_cents = 0
        for task_id, qty in sorted(merged.items()):
            t = tasks[task_id]
            conn.execute(
                """INSERT INTO daily_records
                   (task_id, task_name, task_icon, price, quantity, amount, record_date, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (task_id, t["name"], t["icon"], t["price"], qty,
                 t["price"] * qty, today, now),
            )
            added_cents += t["price"] * qty

        total = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM daily_records WHERE record_date = ?",
            (today,),
        ).fetchone()[0]

    return {
        "date": today,
        "added": len(merged),
        "added_amount": to_yuan(added_cents),   # 本次提交新增金额，用于儿童端 "+2.5 元" 反馈
        "today_total": to_yuan(total),          # 今日累计
    }


@router.get("/history")
def history(month: str = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")):
    """按月返回每日汇总，默认当月；month 格式 YYYY-MM。"""
    month = month or today_str()[:7]
    with db() as conn:
        rows = conn.execute(
            """SELECT record_date, COUNT(*) AS times,
                      COALESCE(SUM(quantity), 0) AS qty,
                      COALESCE(SUM(amount), 0) AS total
               FROM daily_records WHERE record_date LIKE ?
               GROUP BY record_date ORDER BY record_date DESC""",
            (month + "-%",),
        ).fetchall()
    return {
        "month": month,
        "month_total": to_yuan(sum(r["total"] for r in rows)),
        "days": [
            {"date": r["record_date"], "times": r["times"],
             "quantity": r["qty"], "total": to_yuan(r["total"])}
            for r in rows
        ],
    }


@router.get("/summary")
def summary():
    """今日 / 本月 / 累计收益 + 累计打卡天数（小金库页顶部数字）。"""
    today = today_str()
    month = today[:7]
    with db() as conn:
        def one(sql, *args):
            return conn.execute(sql, args).fetchone()[0]
        return {
            "today_date": today,
            "today_total": to_yuan(one(
                "SELECT COALESCE(SUM(amount),0) FROM daily_records WHERE record_date = ?", today)),
            "month_total": to_yuan(one(
                "SELECT COALESCE(SUM(amount),0) FROM daily_records WHERE record_date LIKE ?",
                month + "-%")),
            "grand_total": to_yuan(one(
                "SELECT COALESCE(SUM(amount),0) FROM daily_records")),
            "checked_days": one("SELECT COUNT(DISTINCT record_date) FROM daily_records"),
        }
