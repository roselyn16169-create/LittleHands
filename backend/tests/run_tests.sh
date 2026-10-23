#!/usr/bin/env bash
# 接口回归测试一键脚本：自动重置测试库、启动服务、跑儿童端+家长端断言、恢复原库。
# 用法（任意目录均可）：bash backend/tests/run_tests.sh
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
  "$PY" -m uvicorn main:app --port "$PORT" > /tmp/chore_test_server.log 2>&1 &
  BOOT_PID=$!
  for _ in $(seq 1 30); do
    if curl -s -o /dev/null "http://127.0.0.1:$PORT/api/health"; then return 0; fi
    sleep 0.5
  done
  echo "❗ 服务启动失败，最近日志："
  tail -20 /tmp/chore_test_server.log
  exit 1
}

stop_server() {
  kill "$BOOT_PID" 2>/dev/null || true
  wait "$BOOT_PID" 2>/dev/null || true
  BOOT_PID=""
}

if [ -f "$DB" ]; then
  BACKUP="$(mktemp /tmp/chore_db_backup.XXXXXX)"
  cp "$DB" "$BACKUP"
fi

RC=0
echo "===== 阶段 A：儿童端接口（12 项断言）====="
reset_db
start_server
PORT="$PORT" "$PY" tests/test_child_api.py || RC=1
stop_server

echo "===== 阶段 B：家长端接口（21 项断言）====="
reset_db
start_server
PORT="$PORT" "$PY" tests/test_admin_api.py || RC=1
stop_server

if [ "$RC" -eq 0 ]; then
  echo "🎉 全部接口回归通过（33 项）"
else
  echo "❗ 存在失败用例，请查看上方 ❌ 输出"
fi
exit "$RC"
