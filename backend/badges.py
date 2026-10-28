"""成就徽章：定义、指标实时计算与解锁判定。

设计要点：
- 徽章条件全部由现有数据（打卡记录/结算记录）实时计算，无需冗余计数
- 解锁只在「打卡提交 / 新增结算」时触发判定（check_achievements 随调用方事务提交）
- 造历史数据不会自动解锁——只有孩子的每一次真实动作才点亮徽章
"""
from utils import now_iso

# 12 枚徽章：key 唯一标识；metric 对应 evaluate_metrics 的指标；target 为达成阈值
BADGES = [
    {"key": "streak_3",  "icon": "🔥", "name": "坚持之星·铜", "desc": "连续打卡 3 天",   "metric": "streak",         "target": 3,   "tier": 1, "group": "坚持"},
    {"key": "streak_7",  "icon": "🌟", "name": "坚持之星·银", "desc": "连续打卡 7 天",   "metric": "streak",         "target": 7,   "tier": 2, "group": "坚持"},
    {"key": "streak_30", "icon": "🎖️", "name": "坚持之星·金", "desc": "连续打卡 30 天",  "metric": "streak",         "target": 30,  "tier": 3, "group": "坚持"},
    {"key": "days_10",   "icon": "📅", "name": "勤劳 10 天",   "desc": "累计打卡 10 天",  "metric": "days",           "target": 10,  "tier": 1, "group": "勤劳"},
    {"key": "days_50",   "icon": "🏆", "name": "勤劳 50 天",   "desc": "累计打卡 50 天",  "metric": "days",           "target": 50,  "tier": 2, "group": "勤劳"},
    {"key": "task_20",   "icon": "🧹", "name": "单项小能手",   "desc": "同一项家务累计 20 次（从第一天起算，非单日）", "metric": "max_task_times", "target": 20, "tier": 2, "group": "技能"},
    {"key": "kinds_5",   "icon": "⭐", "name": "多面手",       "desc": "单日完成 5 种不同家务", "metric": "max_day_kinds", "target": 5,  "tier": 1, "group": "技能"},
    {"key": "money_10",  "icon": "💰", "name": "小富翁·铜",   "desc": "累计赚取 10 元",  "metric": "money",          "target": 10,  "tier": 1, "group": "财富"},
    {"key": "money_50",  "icon": "💎", "name": "小富翁·银",   "desc": "累计赚取 50 元",  "metric": "money",          "target": 50,  "tier": 2, "group": "财富"},
    {"key": "money_100", "icon": "👑", "name": "小富翁·金",   "desc": "累计赚取 100 元", "metric": "money",          "target": 100, "tier": 3, "group": "财富"},
    {"key": "settle_1",  "icon": "🎁", "name": "首次兑换",     "desc": "第一次兑换奖励",   "metric": "settles",        "target": 1,   "tier": 1, "group": "兑换"},
    {"key": "settle_5",  "icon": "🛍️", "name": "兑换爱好者",   "desc": "累计兑换 5 次",   "metric": "settles",        "target": 5,   "tier": 2, "group": "兑换"},
]


def evaluate_metrics(conn) -> dict:
    """实时计算全部徽章指标（金额单位：元）。"""
    from datetime import date, timedelta
    rows = [r[0] for r in conn.execute(
        "SELECT DISTINCT record_date FROM daily_records ORDER BY record_date DESC")]
    streak = 0
    if rows:
        expect = date.fromisoformat(rows[0])
        for d in rows:
            if date.fromisoformat(d) == expect:
                streak += 1
                expect -= timedelta(days=1)
            else:
                break
    money = conn.execute("SELECT COALESCE(SUM(amount),0) FROM daily_records").fetchone()[0] / 100
    settles = conn.execute("SELECT COUNT(*) FROM settlements").fetchone()[0]
    top = conn.execute(
        """SELECT task_name, task_icon, SUM(quantity) AS c FROM daily_records
           GROUP BY task_id ORDER BY c DESC LIMIT 1""").fetchone()
    max_task = top["c"] if top else 0
    top_task = ({"name": top["task_name"], "icon": top["task_icon"], "count": top["c"]}
                if top else None)
    max_kinds = conn.execute(
        "SELECT COALESCE(MAX(k),0) FROM (SELECT COUNT(DISTINCT task_id) k FROM daily_records GROUP BY record_date)"
    ).fetchone()[0]
    return {"streak": streak, "days": len(rows), "money": round(money, 2),
            "settles": settles, "max_task_times": max_task,
            "max_day_kinds": max_kinds, "top_task": top_task}


def check_achievements(conn) -> list:
    """在打卡/结算事务内调用：判定新解锁徽章、写入表并返回新解锁列表（不 commit）。"""
    metrics = evaluate_metrics(conn)
    unlocked = {r[0] for r in conn.execute("SELECT badge_key FROM achievements")}
    fresh = []
    for b in BADGES:
        if b["key"] in unlocked:
            continue
        if metrics[b["metric"]] >= b["target"]:
            conn.execute(
                "INSERT INTO achievements (badge_key, unlocked_at) VALUES (?, ?)",
                (b["key"], now_iso()))
            fresh.append(b)
    return fresh


def badges_payload(conn) -> dict:
    """成就墙数据：指标 + 全量徽章（含解锁状态、当前进度）。"""
    metrics = evaluate_metrics(conn)
    got = {r["badge_key"]: r["unlocked_at"]
           for r in conn.execute("SELECT badge_key, unlocked_at FROM achievements")}
    badges = []
    for b in BADGES:
        cur = metrics[b["metric"]]
        badges.append({**b, "current": min(cur, b["target"]),
                       "unlocked": b["key"] in got, "unlocked_at": got.get(b["key"])})
    return {"metrics": metrics, "badges": badges}
