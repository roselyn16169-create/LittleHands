"""成就徽章专项测试（阶段 C，10 项断言）。

跨天场景（连续打卡等）无法通过 API 造数，由本测试直接向测试库写入历史打卡记录；
其余全部通过 HTTP 接口驱动验证。
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


# ---------- 前置：造历史数据（昨天/前天/大前天连续 3 天 + 8/9 天前断档 2 天） ----------
today = datetime.date.today()
dates = [(today - datetime.timedelta(days=i)).isoformat() for i in (1, 2, 3, 8, 9)]
conn = sqlite3.connect(DB)
for d in dates:
    conn.execute(
        "INSERT INTO daily_records (task_id, task_name, task_icon, price, quantity, amount, record_date, created_at)"
        " VALUES (1, '扫地', '🧹', 150, 1, 150, ?, ?)", (d, d + "T10:00:00"))
conn.commit()
conn.close()

# ---------- 用例 ----------

s, b = call("GET", "/api/achievements")
check("成就墙返回 12 枚徽章，造数不触发解锁（均未点亮）",
      s == 200 and len(b["badges"]) == 12 and all(not x["unlocked"] for x in b["badges"]),
      f"{s} n={len(b.get('badges', []))}")
check("指标实时计算正确（连续 3 天 / 累计 5 天 / 7.5 元）",
      b["metrics"]["streak"] == 3 and b["metrics"]["days"] == 5
      and abs(b["metrics"]["money"] - 7.5) < 1e-9, str(b["metrics"]))

s, b = call("POST", "/api/records/submit", {"items": [{"task_id": 1, "quantity": 1}]})
keys = [x["key"] for x in b.get("unlocked", [])]
check("今日打卡点亮「坚持之星·铜」（连续 4 天），不误触发 10 天徽章",
      s == 200 and "streak_3" in keys and "days_10" not in keys, str(keys))

s, b = call("POST", "/api/records/submit", {"items": [{"task_id": 2, "quantity": 5}]})
keys = [x["key"] for x in b.get("unlocked", [])]
check("累计满 10 元点亮「小富翁·铜」", "money_10" in keys, str(keys))

s, b = call("POST", "/api/records/submit", {"items": [{"task_id": 7, "quantity": 20}]})
keys = [x["key"] for x in b.get("unlocked", [])]
check("同一家务满 20 次点亮「单项小能手」", "task_20" in keys, str(keys))

s, b = call("POST", "/api/records/submit", {"items": [
    {"task_id": 3, "quantity": 1}, {"task_id": 4, "quantity": 1},
    {"task_id": 5, "quantity": 1}, {"task_id": 6, "quantity": 1},
    {"task_id": 8, "quantity": 1}]})
keys = [x["key"] for x in b.get("unlocked", [])]
check("单日完成 5 种家务点亮「多面手」", "kinds_5" in keys, str(keys))

s, b = call("POST", "/api/records/submit", {"items": [{"task_id": 1, "quantity": 1}]})
check("重复动作不重复解锁（unlocked 为空）", b.get("unlocked") == [], str(b.get("unlocked")))

s, b = call("GET", "/api/achievements")
b3 = next(x for x in b["badges"] if x["key"] == "streak_3")
d10 = next(x for x in b["badges"] if x["key"] == "days_10")
check("成就墙状态与进度正确（已解锁发光 / 未解锁显示还差天数）",
      b3["unlocked"] and b3["unlocked_at"] and not d10["unlocked"] and d10["current"] == 6,
      f"streak_3={b3['unlocked']} days_10.current={d10['current']}")

_, auth = call("POST", "/api/auth/verify", {"pin": "1234"})
TOKEN = auth["token"]
s, b = call("POST", "/api/admin/settlements", {"method": "现金", "amount": 0.01}, token=TOKEN)
keys = [x["key"] for x in b.get("unlocked", [])]
check("首次结算点亮「首次兑换」", s == 201 and keys == ["settle_1"], str(keys))

for _ in range(4):
    s, b = call("POST", "/api/admin/settlements", {"method": "现金", "amount": 0.01}, token=TOKEN)
keys = [x["key"] for x in b.get("unlocked", [])]
check("累计 5 次结算点亮「兑换爱好者」", s == 201 and "settle_5" in keys, str(keys))

s, b = call("GET", "/api/admin/stats", token=TOKEN)
check("家长概览显示成就进度（6 / 12）",
      s == 200 and b["achieved"] == 6 and b["total_badges"] == 12, f"{s} {b.get('achieved')}/{b.get('total_badges')}")

print(f"\n通过 {passed} 项，失败 {failed} 项")
sys.exit(0 if failed == 0 else 1)
