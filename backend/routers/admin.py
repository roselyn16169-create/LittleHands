"""家长后台：PIN 鉴权、任务 CRUD、变更日志、统计。"""
import json
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import check_pin, issue_token, require_parent, revoke_token, set_pin
from database import db
from schemas import PinChange, PinVerify, TaskCreate, TaskUpdate
from utils import make_pinyin, now_iso, today_str, to_cents, to_yuan

router = APIRouter()

# 可编辑字段白名单（SET 子句仅拼接白名单列名，参数走 ?，无注入风险）
EDITABLE_FIELDS = ("name", "pinyin", "icon", "price", "daily_limit", "sort_order", "is_active")


# ---------- 内部工具 ----------

def _write_log(conn, task_id: int, task_name: str, action: str, changes: list) -> None:
    conn.execute(
        """INSERT INTO task_logs (task_id, task_name, action, changes, operator, created_at)
           VALUES (?, ?, ?, ?, 'parent', ?)""",
        (task_id, task_name, action,
         json.dumps(changes, ensure_ascii=False), now_iso()),
    )


def _row_out(r, done_today: int = 0, total_times: int = 0, total_earned: int = 0) -> dict:
    return {
        "id": r["id"], "name": r["name"], "pinyin": r["pinyin"], "icon": r["icon"],
        "price": to_yuan(r["price"]), "daily_limit": r["daily_limit"],
        "sort_order": r["sort_order"], "is_active": bool(r["is_active"]),
        "created_at": r["created_at"], "updated_at": r["updated_at"],
        "done_today": done_today, "total_times": total_times,
        "total_earned": to_yuan(total_earned),
    }


# ---------- PIN 鉴权 ----------

@router.post("/api/auth/verify", tags=["家长后台 · PIN 鉴权"])
def auth_verify(req: PinVerify):
    """PIN 校验，成功返回 2 小时有效的家长 token。"""
    check_pin(req.pin)
    return {"token": issue_token(), "expires_in": 7200}


@router.post("/api/auth/logout", tags=["家长后台 · PIN 鉴权"])
def auth_logout(token: str = Depends(require_parent)):
    """退出锁屏，作废当前 token。"""
    revoke_token(token)
    return {"status": "locked"}


@router.put("/api/auth/pin", tags=["家长后台 · PIN 鉴权"])
def auth_change_pin(req: PinChange, _t: str = Depends(require_parent)):
    """修改 PIN：需已解锁 + 旧 PIN 正确。"""
    check_pin(req.old_pin)
    set_pin(req.new_pin)
    return {"status": "ok"}


# ---------- 任务管理 ----------

@router.get("/api/admin/tasks", tags=["家长后台 · 任务管理"])
def admin_list_tasks(_t: str = Depends(require_parent)):
    """全部任务（含已下架，下架排最后），附今日/累计打卡统计。"""
    today = today_str()
    with db() as conn:
        tasks = conn.execute(
            "SELECT * FROM tasks ORDER BY is_active DESC, sort_order, id").fetchall()
        today_map = {r["task_id"]: r["d"] for r in conn.execute(
            """SELECT task_id, SUM(quantity) AS d FROM daily_records
               WHERE record_date = ? GROUP BY task_id""", (today,))}
        all_map = {r["task_id"]: (r["q"], r["a"]) for r in conn.execute(
            """SELECT task_id, SUM(quantity) AS q, SUM(amount) AS a FROM daily_records
               GROUP BY task_id""")}
    return {"tasks": [
        _row_out(t,
                 done_today=today_map.get(t["id"], 0),
                 total_times=all_map.get(t["id"], (0, 0))[0],
                 total_earned=all_map.get(t["id"], (0, 0))[1])
        for t in tasks
    ]}


@router.post("/api/admin/tasks", status_code=201, tags=["家长后台 · 任务管理"])
def admin_create_task(req: TaskCreate, _t: str = Depends(require_parent)):
    """新增家务；拼音缺省时自动生成，动作写入变更日志。"""
    name = req.name.strip()
    if not name:
        raise HTTPException(400, "名称不能为空白")
    pinyin = (req.pinyin or "").strip() or make_pinyin(name)
    price = to_cents(req.price)
    if price <= 0:
        raise HTTPException(400, "单价至少 0.01 元")
    sort_no = 99 if req.sort_order is None else req.sort_order   # 新任务默认排最后
    now = now_iso()
    with db() as conn:
        cur = conn.execute(
            """INSERT INTO tasks
               (name, pinyin, icon, price, daily_limit, sort_order, is_active, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)""",
            (name, pinyin, req.icon, price, req.daily_limit, sort_no, now, now))
        new_id = cur.lastrowid
        _write_log(conn, new_id, name, "create", [
            {"field": "name", "old": None, "new": name},
            {"field": "pinyin", "old": None, "new": pinyin},
            {"field": "icon", "old": None, "new": req.icon},
            {"field": "price", "old": None, "new": to_yuan(price)},
            {"field": "daily_limit", "old": None, "new": req.daily_limit},
        ])
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (new_id,)).fetchone()
    return _row_out(row)


@router.put("/api/admin/tasks/{task_id}", tags=["家长后台 · 任务管理"])
def admin_update_task(task_id: int, req: TaskUpdate, _t: str = Depends(require_parent)):
    """局部更新：只改传入字段；名称变化且未手动指定拼音时自动重生成；diff 写入日志。"""
    data = req.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(400, "没有需要更新的字段")

    # 拼音传空 = 视为未提供（交给自动生成逻辑）
    if "pinyin" in data and not (data["pinyin"] or "").strip():
        data.pop("pinyin")

    if "name" in data:
        name = data["name"].strip()
        if not name:
            raise HTTPException(400, "名称不能为空白")
        data["name"] = name

    with db() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "家务不存在")

        # 名称变了且未显式提供拼音 -> 自动重生成
        if "name" in data and data["name"] != row["name"] and "pinyin" not in data:
            data["pinyin"] = make_pinyin(data["name"])

        sets, params, changes = [], [], []
        for col in EDITABLE_FIELDS:
            if col not in data:
                continue
            new_raw = data[col]
            if col == "price":
                new_raw = to_cents(new_raw)
                if new_raw <= 0:
                    raise HTTPException(400, "单价至少 0.01 元")
            elif col == "is_active":
                new_raw = int(new_raw)
            if new_raw == row[col]:
                continue                                  # 值没变，跳过且不记日志

            sets.append(f"{col} = ?")
            params.append(new_raw)
            if col == "price":
                old_d, new_d = to_yuan(row[col]), to_yuan(new_raw)   # 日志里用「元」展示
            elif col == "is_active":
                old_d, new_d = bool(row[col]), bool(new_raw)
            else:
                old_d, new_d = row[col], new_raw
            changes.append({"field": col, "old": old_d, "new": new_d})

        if not sets:
            raise HTTPException(400, "内容没有变化")

        sets.append("updated_at = ?")
        params.extend([now_iso(), task_id])
        conn.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE id = ?", params)
        _write_log(conn, task_id, data.get("name", row["name"]), "update", changes)
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return _row_out(row)


@router.delete("/api/admin/tasks/{task_id}", tags=["家长后台 · 任务管理"])
def admin_delete_task(task_id: int, _t: str = Depends(require_parent)):
    """下架（软删除）：历史记录完整保留，编辑 is_active=true 可重新上架。"""
    with db() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "家务不存在")
        if not row["is_active"]:
            return {"id": task_id, "status": "already_inactive"}   # 幂等，不重复记日志
        conn.execute("UPDATE tasks SET is_active = 0, updated_at = ? WHERE id = ?",
                     (now_iso(), task_id))
        _write_log(conn, task_id, row["name"], "delete",
                   [{"field": "is_active", "old": True, "new": False}])
    return {"id": task_id, "status": "deleted"}


# ---------- 日志与统计 ----------

@router.get("/api/admin/logs", tags=["家长后台 · 日志与统计"])
def admin_logs(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
               _t: str = Depends(require_parent)):
    """变更日志，最新在前，分页。"""
    with db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM task_logs").fetchone()[0]
        rows = conn.execute(
            "SELECT * FROM task_logs ORDER BY id DESC LIMIT ? OFFSET ?",
            (page_size, (page - 1) * page_size),
        ).fetchall()
    return {
        "total": total, "page": page, "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
        "items": [
            {"id": r["id"], "task_id": r["task_id"], "task_name": r["task_name"],
             "action": r["action"], "changes": json.loads(r["changes"]),
             "operator": r["operator"], "created_at": r["created_at"]}
            for r in rows
        ],
    }


@router.get("/api/admin/stats", tags=["家长后台 · 日志与统计"])
def admin_stats(_t: str = Depends(require_parent)):
    """后台概览：今日/本月/累计收益、打卡天数、近 7 天趋势（缺数日补零）。"""
    today = date.today()
    month = today.strftime("%Y-%m")
    start = (today - timedelta(days=6)).isoformat()
    with db() as conn:
        def one(sql, *a):
            return conn.execute(sql, a).fetchone()[0]
        day_map = {r["record_date"]: r["t"] for r in conn.execute(
            "SELECT record_date, SUM(amount) AS t FROM daily_records "
            "WHERE record_date >= ? GROUP BY record_date", (start,))}
        result = {
            "today_total": to_yuan(one(
                "SELECT COALESCE(SUM(amount),0) FROM daily_records WHERE record_date = ?",
                today.isoformat())),
            "month_total": to_yuan(one(
                "SELECT COALESCE(SUM(amount),0) FROM daily_records WHERE record_date LIKE ?",
                month + "-%")),
            "grand_total": to_yuan(one("SELECT COALESCE(SUM(amount),0) FROM daily_records")),
            "checked_days": one("SELECT COUNT(DISTINCT record_date) FROM daily_records"),
            "active_tasks": one("SELECT COUNT(*) FROM tasks WHERE is_active = 1"),
        }
    last7 = []
    for i in range(6, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        last7.append({"date": d, "total": to_yuan(day_map.get(d, 0))})
    result["last7"] = last7
    return result
