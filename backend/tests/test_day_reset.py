"""跨天重置专项测试（阶段 E，4 项断言）。

验证「第二天打卡次数自动归零」——用户明确要求的核心行为：
昨天打满上限的家务今天额度恢复不置灰、今日明细为空、累计收入与历史记录完整保留。
需环境变量：PORT（服务端口）、CHORE_DB（测试库路径），由 run_tests.sh 提供。
"""
import datetime
import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request

PORT = os.environ.get("PORT", "8399")
DB = os.environ["CHORE_DB"]
BASE = f"http://127.0.0.1:{PORT}"
passed, failed = 0, 0


def call(method, path, body=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def check(name, cond, extra=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        print(f"  ❌ {name}  {extra}")


# ---------- 前置：昨天扫地打满上限（置灰场景）、拖地打 2 次 ----------
yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()

_, auth = call("POST", "/api/auth/verify", {"pin": "1234"})
call("PUT", "/api/admin/tasks/1", {"daily_limit": 1}, token=auth["token"])   # 扫地限 1 次/天

c = sqlite3.connect(DB)
for tid, name, icon, price, qty in [(1, "扫地", "🧹", 150, 1), (2, "拖地", "🪣", 200, 2)]:
    c.execute(
        "INSERT INTO daily_records (task_id, task_name, task_icon, price, quantity, amount, record_date, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (tid, name, icon, price, qty, price * qty, yesterday, yesterday + "T20:00:00"))
c.commit()
c.close()

# ---------- 用例 ----------

s, b = call("GET", "/api/tasks")
saodi = next(t for t in b["tasks"] if t["name"] == "扫地")
check("E1 昨天打满的家务今天归零（次数 0 / 额度恢复 / 不置灰）",
      s == 200 and saodi["done_today"] == 0 and saodi["remain_today"] == 1
      and all(t["done_today"] == 0 for t in b["tasks"]),
      f"扫地 done={saodi['done_today']} remain={saodi['remain_today']}")

s, b = call("GET", "/api/records/today")
check("E2 今日明细为空、今日合计 0",
      s == 200 and b["total"] == 0 and len(b["items"]) == 0, f"{s} {b}")

s, b = call("GET", "/api/records/summary")
check("E3 累计收入完整保留昨天的钱（¥5.5）",
      s == 200 and abs(b["grand_total"] - 5.5) < 1e-9 and abs(b["balance"] - 5.5) < 1e-9,
      f"{s} {b}")

s, b = call("GET", f"/api/records?date={yesterday}")
check("E4 按日回看昨天：记录完整（2 项 / ¥5.5）",
      s == 200 and len(b["items"]) == 2 and abs(b["total"] - 5.5) < 1e-9, f"{s} {b}")

print(f"\n通过 {passed} 项，失败 {failed} 项")
sys.exit(0 if failed == 0 else 1)
