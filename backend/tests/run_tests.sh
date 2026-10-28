#!/usr/bin/env bash
# ============================================================
# LittleHands 小手家务 · 一键回归测试
# 阶段 A 儿童端接口（12 项） / 阶段 B 家长端接口（33 项）
# 阶段 C 成就徽章（11 项）     / 阶段 D 页面静态断言（6 项）
# 共 62 项。详见 docs/TEST_PLAN.md
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
echo "===== 阶段 A：儿童端接口（12 项断言）====="
reset_db
start_server
PORT="$PORT" "$PY" tests/test_child_api.py || RC=1
stop_server

echo "===== 阶段 B：家长端接口（33 项断言）====="
reset_db
start_server
PORT="$PORT" "$PY" tests/test_admin_api.py || RC=1
stop_server

echo "===== 阶段 C：成就徽章（11 项断言）====="
reset_db
start_server
PORT="$PORT" CHORE_DB="$DB" "$PY" tests/test_achievements.py || RC=1
stop_server

echo "===== 阶段 D：页面静态断言（6 项）====="
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
stop_server
echo "阶段 D：通过 $DP 项，失败 $DF 项"
[ "$DF" -gt 0 ] && RC=1

if [ "$RC" -eq 0 ]; then
  echo "🎉 全部回归通过（62 项：A12 + B33 + C11 + D6）"
else
  echo "❗ 存在失败用例，请查看上方 ❌ 输出"
fi
exit "$RC"
