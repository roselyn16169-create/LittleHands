"""儿童端接口回归测试（第 2 步，11 项断言）。

独立运行前需先启动服务，例如：
    cd backend && ../.venv/bin/uvicorn main:app --port 8399
    PORT=8399 ../.venv/bin/python tests/test_child_api.py
或直接使用一键脚本：bash tests/run_tests.sh
"""
import datetime
import json
import os
import sys
import urllib.error
import urllib.request

PORT = os.environ.get("PORT", "8399")
BASE = f"http://127.0.0.1:{PORT}"
passed, failed = 0, 0


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
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


today = datetime.date.today().isoformat()

s, b = call("GET", "/api/tasks")
check("GET /api/tasks 返回 8 项上架家务", s == 200 and len(b["tasks"]) == 8, f"{s} {b}")

s, b = call("POST", "/api/records/submit",
            {"items": [{"task_id": 1, "quantity": 1}, {"task_id": 7, "quantity": 2}]})
check("提交 扫地x1 + 收拾玩具x2（共 2.0 元）",
      s == 200 and abs(b["today_total"] - 2.0) < 1e-9 and abs(b["added_amount"] - 2.0) < 1e-9,
      f"{s} {b}")

s, b = call("GET", "/api/tasks")
t1 = next(t for t in b["tasks"] if t["id"] == 1)
t7 = next(t for t in b["tasks"] if t["id"] == 7)
check("列表回显：扫地 done=1 / remain=0", t1["done_today"] == 1 and t1["remain_today"] == 0)
check("列表回显：收拾玩具 done=2 / remain=1", t7["done_today"] == 2 and t7["remain_today"] == 1)

s, b = call("POST", "/api/records/submit", {"items": [{"task_id": 7, "quantity": 2}]})
check("超额提交被整体拒绝（400）", s == 400, f"{s} {b}")

s, b = call("POST", "/api/records/submit", {"items": [{"task_id": 7, "quantity": 1}]})
check("补打 1 次恰好到上限，今日累计 2.5 元",
      s == 200 and abs(b["today_total"] - 2.5) < 1e-9, f"{s} {b}")

s, b = call("GET", "/api/records/today")
check("今日明细 3 条（追加制：每次提交一行）、合计 2.5 元",
      s == 200 and len(b["items"]) == 3 and abs(b["total"] - 2.5) < 1e-9, f"{s} {b}")

s, b = call("GET", f"/api/records?date={today}")
check("按日期查询正常", s == 200 and abs(b["total"] - 2.5) < 1e-9)
s, b = call("GET", "/api/records?date=2026-13-99")
check("非法日期返回 400", s == 400, f"{s} {b}")

s, b = call("GET", "/api/records/history")
check("按月历史：本月合计 2.5 元、今天 3 条记录共 4 次",
      s == 200 and abs(b["month_total"] - 2.5) < 1e-9 and b["days"][0]["times"] == 3
      and b["days"][0]["quantity"] == 4, f"{s} {b}")

s, b = call("GET", "/api/records/summary")
check("汇总：累计 2.5 元、打卡 1 天",
      s == 200 and abs(b["grand_total"] - 2.5) < 1e-9 and b["checked_days"] == 1, f"{s} {b}")

print(f"\n通过 {passed} 项，失败 {failed} 项")
sys.exit(0 if failed == 0 else 1)
