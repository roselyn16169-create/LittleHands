"""家长端接口回归测试（第 3 步，21 项断言）。

独立运行前需先启动服务，例如：
    cd backend && ../.venv/bin/uvicorn main:app --port 8399
    PORT=8399 ../.venv/bin/python tests/test_admin_api.py
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


s, b = call("GET", "/api/admin/tasks")
check("未带 token 访问家长接口被拒（401）", s == 401, f"{s} {b}")

s, b = call("POST", "/api/auth/verify", {"pin": "9999"})
check("错误 PIN 返回 401", s == 401, f"{s} {b}")

s, b = call("POST", "/api/auth/verify", {"pin": "1234"})
check("正确 PIN 换取 token", s == 200 and b.get("token") and b["expires_in"] > 0, f"{s} {b}")
TOKEN = b["token"]

s, b = call("GET", "/api/admin/tasks", token=TOKEN)
check("后台任务列表 8 项（含统计字段）", s == 200 and len(b["tasks"]) == 8
      and b["tasks"][0]["done_today"] == 0, f"{s}")

s, b = call("POST", "/api/admin/tasks",
            {"name": "擦窗户", "icon": "🪟", "price": 2, "daily_limit": 1}, token=TOKEN)
check("新增「擦窗户」并自动生成拼音",
      s == 201 and b["pinyin"] == "cā chuāng hù", f"{s} {b}")
TID = b["id"]

s, b = call("PUT", f"/api/admin/tasks/{TID}", {"price": 3}, token=TOKEN)
check("改价为 3 元", s == 200 and abs(b["price"] - 3.0) < 1e-9, f"{s} {b}")

s, b = call("PUT", f"/api/admin/tasks/{TID}", {"name": "浇阳台的花"}, token=TOKEN)
check("改名后拼音自动更新", s == 200 and b["pinyin"] == "jiāo yáng tái de huā", f"{s} {b}")

s, b = call("POST", "/api/records/submit", {"items": [{"task_id": TID, "quantity": 1}]})
check("儿童端可打卡新任务（3.0 元）", s == 200 and abs(b["today_total"] - 3.0) < 1e-9, f"{s} {b}")

s, b = call("DELETE", f"/api/admin/tasks/{TID}", token=TOKEN)
check("下架任务", s == 200 and b["status"] == "deleted", f"{s} {b}")
s, b = call("GET", "/api/tasks")
check("下架后儿童端只剩 8 项", len(b["tasks"]) == 8)
s, b = call("GET", "/api/records/today")
check("历史打卡记录仍保留（快照机制）", any(i["task_id"] == TID for i in b["items"]))

s, b = call("PUT", f"/api/admin/tasks/{TID}", {"is_active": True}, token=TOKEN)
check("重新上架", s == 200 and b["is_active"] is True, f"{s} {b}")

s, b = call("GET", "/api/admin/tasks", token=TOKEN)
t = next(t for t in b["tasks"] if t["id"] == TID)
check("后台统计：该任务今日 1 次、累计 3.0 元",
      t["done_today"] == 1 and abs(t["total_earned"] - 3.0) < 1e-9)

s, b = call("GET", "/api/admin/logs", token=TOKEN)
actions = {i["action"] for i in b["items"]}
check("变更日志完整记录 create/update/delete",
      s == 200 and {"create", "update", "delete"} <= actions and b["total"] >= 4,
      f"{s} total={b.get('total')}")

s, b = call("GET", "/api/admin/logs?page=1&page_size=2", token=TOKEN)
check("日志分页（每页 2 条）",
      s == 200 and len(b["items"]) == 2 and b["pages"] == (b["total"] + 1) // 2)

s, b = call("GET", "/api/admin/stats", token=TOKEN)
today = datetime.date.today().isoformat()
check("统计：累计 3.0 元、近 7 天趋势含今日",
      s == 200 and abs(b["grand_total"] - 3.0) < 1e-9 and len(b["last7"]) == 7
      and b["last7"][-1]["date"] == today and abs(b["last7"][-1]["total"] - 3.0) < 1e-9, f"{s} {b}")

s, b = call("POST", "/api/admin/tasks", {"name": "测试", "price": 0.001}, token=TOKEN)
check("非法单价（<0.01 元）被拒 422", s == 422, f"{s}")

s, b = call("PUT", "/api/auth/pin", {"old_pin": "1234", "new_pin": "5678"}, token=TOKEN)
check("修改 PIN", s == 200, f"{s} {b}")
s, b = call("POST", "/api/auth/logout", token=TOKEN)
check("退出锁屏", s == 200, f"{s} {b}")
s, b = call("GET", "/api/admin/tasks", token=TOKEN)
check("登出后旧 token 失效（401）", s == 401)
s, b = call("POST", "/api/auth/verify", {"pin": "5678"})
check("新 PIN 可正常登录", s == 200, f"{s} {b}")

print(f"\n通过 {passed} 项，失败 {failed} 项")
sys.exit(0 if failed == 0 else 1)
