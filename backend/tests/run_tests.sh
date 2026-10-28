#!/usr/bin/env bash
# ============================================================
# LittleHands 小手家务 · 一键回归测试
# 阶段 A 儿童端接口（13 项） / 阶段 B 家长端接口（33 项）
# 阶段 C 成就徽章（12 项）     / 阶段 D 页面静态断言（9 项）
# 阶段 E 跨天重置（4 项）      / 共 71 项。详见 docs/TEST_PLAN.md
# 用法（任意目录）：bash backend/tests/run_tests.sh
# ============================================================
set -e

BACKEND_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ROOT_DIR="$(cd "$BACKEND_DIR/.." && pwd)"
PY="$ROOT_DIR/.venv/bin/python"
[ -x "$PY" ] || PY="python3"
DB="$ROOT_DIR/data/chore.db"
PORT="${PORT:-8399}"
BOOT_PID=""
BACKUP=""

cleanup() {
  if [ -n "$BOOT_PID" ]; then kill "$BOOT_PID" 2>/dev/null || true; fi
  if [ -n "$BACKUP" ] && [ -f "$BACKUP" ]; then
    mv -f "$BACKUP" "$DB"
    echo "（已恢复原有数据库）"
  else
    rm -f "$DB" "$DB-journal" "$DB-wal" "$DB-shm"
    echo "（测试库已清理，服务下次启动自动重建种子数据）"
  fi
}
trap cleanup EXIT

cd "$BACKEND_DIR"

reset_db() {
  rm -f "$DB" "$DB-journal" "$DB-wal" "$DB-shm"
}

start_server() {
  "$PY" -m uvicorn main:app --port "$PORT" > /tmp/lh_test_server.log 2>&1 &
  BOOT_PID=$!
  for _ in $(seq 1 30); do
    if curl -s -o /dev/null "http://127.0.0.1:$PORT/api/health"; then return 0; fi
    sleep 0.5
  done
  echo "❗ 服务启动失败，最近日志："
  tail -20 /tmp/lh_test_server.log
  exit 1
}

stop_server() {
  kill "$BOOT_PID" 2>/dev/null || true
  wait "$BOOT_PID" 2>/dev/null || true
  BOOT_PID=""
}

if [ -f "$DB" ]; then
  BACKUP="$(mktemp /tmp/lh_db_backup.XXXXXX)"
  cp "$DB" "$BACKUP"
fi

RC=0
echo "===== 阶段 A：儿童端接口（13 项断言）====="
reset_db
start_server
PORT="$PORT" "$PY" tests/test_child_api.py || RC=1
stop_server

echo "===== 阶段 B：家长端接口（33 项断言）====="
reset_db
start_server
PORT="$PORT" "$PY" tests/test_admin_api.py || RC=1
stop_server

echo "===== 阶段 C：成就徽章（12 项断言）====="
reset_db
start_server
PORT="$PORT" CHORE_DB="$DB" "$PY" tests/test_achievements.py || RC=1
stop_server

echo "===== 阶段 D：页面静态断言（9 项）====="
reset_db
start_server
DP=0; DF=0
ck() { if [ "$2" = "1" ]; then DP=$((DP+1)); echo "  ✅ $1"; else DF=$((DF+1)); echo "  ❌ $1"; fi; }
B="http://127.0.0.1:$PORT"
[ "$(curl -s -o /dev/null -w '%{http_code}' "$B/")" = "200" ] && ck "儿童端页面可访问" 1 || ck "儿童端页面可访问" 0
[ "$(curl -s -o /dev/null -w '%{http_code}' "$B/admin.html")" = "200" ] && ck "家长后台页面可访问" 1 || ck "家长后台页面可访问" 0
if curl -s "$B/admin.html" | grep -q "btn-logout"; then ck "后台无锁屏按钮（单会话模式）" 0; else ck "后台无锁屏按钮（单会话模式）" 1; fi
if grep -q "localStorage" "$ROOT_DIR/frontend/js/api.js"; then ck "登录凭证不写入浏览器存储" 0; else ck "登录凭证不写入浏览器存储" 1; fi
if curl -sI "$B/admin.html" | grep -qi "cache-control: no-cache"; then ck "页面响应带 no-cache（改版即生效）" 1; else ck "页面响应带 no-cache（改版即生效）" 0; fi
NB=$(curl -s "$B/api/achievements" | "$PY" -c "import json,sys; print(len(json.load(sys.stdin)['badges']))" 2>/dev/null)
[ "$NB" = "12" ] && ck "成就接口返回 12 枚徽章" 1 || ck "成就接口返回 12 枚徽章" 0
UNIQ=$(curl -s "$B/api/achievements" | "$PY" -c "import json,sys; d=json.load(sys.stdin)['badges']; print(1 if len(set(b['icon'] for b in d))==len(d) else 0)" 2>/dev/null)
ck "勋章图标全表不重复（等级可区分）" "$UNIQ"
curl -s "$B/" | grep -q 'id="balance-main"' && ck "儿童端「我的钱」主数字元素就绪" 1 || ck "儿童端「我的钱」主数字元素就绪" 0
if curl -s "$B/" | grep -q "award-overlay" && curl -s "$B/" | grep -q "badge-modal"; then ck "授勋仪式与勋章详情弹层就绪" 1; else ck "授勋仪式与勋章详情弹层就绪" 0; fi
stop_server
echo "阶段 D：通过 $DP 项，失败 $DF 项"
[ "$DF" -gt 0 ] && RC=1

echo "===== 阶段 E：跨天重置（4 项断言）====="
reset_db
start_server
PORT="$PORT" CHORE_DB="$DB" "$PY" tests/test_day_reset.py || RC=1
stop_server

if [ "$RC" -eq 0 ]; then
  echo "🎉 全部回归通过（71 项：A13 + B33 + C12 + D9 + E4）"
else
  echo "❗ 存在失败用例，请查看上方 ❌ 输出"
fi
exit "$RC"
