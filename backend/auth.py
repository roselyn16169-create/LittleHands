"""家长后台鉴权：PIN 校验（SHA-256 存储）、持久化 token（SQLite，服务重启不掉线）、防孩子乱试锁定。"""
import hashlib
import secrets
import time
from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from database import db
from utils import now_iso

TOKEN_TTL = 7 * 24 * 60 * 60   # token 有效期：7 天（存 SQLite，重启依然有效）
MAX_FAILS = 5                  # 连续输错 5 次
LOCK_SECONDS = 30              # 锁定 30 秒

# PIN 连续失败计数仅存内存（重启清零无妨）
_fail_count = 0
_locked_until = 0.0


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _stored_pin_hash(conn) -> Optional[str]:
    """读取 PIN 哈希；兼容早期明文存储，首次读取自动升级为哈希。"""
    row = conn.execute("SELECT value FROM settings WHERE key = 'pin'").fetchone()
    if row is None:
        return None
    value = row[0]
    if len(value) == 64:                      # 已是 sha256 hex
        return value
    conn.execute("UPDATE settings SET value = ? WHERE key = 'pin'", (_sha256(value),))
    return _sha256(value)


def check_pin(pin: str) -> None:
    """校验 PIN，失败抛 401 / 429（连续失败会临时锁定）。"""
    global _fail_count, _locked_until
    now = time.time()
    if now < _locked_until:
        raise HTTPException(429, f"尝试次数过多，请 {int(_locked_until - now) + 1} 秒后再试")
    with db() as conn:
        stored = _stored_pin_hash(conn)
    if stored is not None and secrets.compare_digest(stored, _sha256(pin)):
        _fail_count = 0
        return
    _fail_count += 1
    if _fail_count >= MAX_FAILS:
        _locked_until = now + LOCK_SECONDS
        _fail_count = 0
    raise HTTPException(401, "PIN 码错误")


def set_pin(new_pin: str) -> None:
    with db() as conn:
        conn.execute("UPDATE settings SET value = ? WHERE key = 'pin'", (_sha256(new_pin),))


# ---------- 会话 token（SQLite 持久化） ----------

def issue_token() -> str:
    """签发新 token 并清理全部过期 token。"""
    token = secrets.token_hex(16)
    now = time.time()
    with db() as conn:
        conn.execute("DELETE FROM auth_tokens WHERE expires_at < ?", (now,))
        conn.execute(
            "INSERT INTO auth_tokens (token, expires_at, created_at) VALUES (?, ?, ?)",
            (token, now + TOKEN_TTL, now_iso()),
        )
    return token


def verify_token(token: str) -> bool:
    with db() as conn:
        row = conn.execute(
            "SELECT expires_at FROM auth_tokens WHERE token = ?", (token,)).fetchone()
        if row is None:
            return False
        if time.time() > row["expires_at"]:
            conn.execute("DELETE FROM auth_tokens WHERE token = ?", (token,))
            return False
    return True


def revoke_token(token: str) -> None:
    with db() as conn:
        conn.execute("DELETE FROM auth_tokens WHERE token = ?", (token,))


# HTTPBearer 让 Swagger /docs 出现「Authorize」按钮，可直接粘贴 token 调试
_bearer = HTTPBearer(auto_error=False, description="POST /api/auth/verify 获取")

def require_parent(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> str:
    """家长接口统一依赖：校验 Authorization: Bearer <token>。"""
    if creds is None:
        raise HTTPException(401, "请先输入 PIN 解锁家长后台")
    if not verify_token(creds.credentials):
        raise HTTPException(401, "登录已过期，请重新输入 PIN")
    return creds.credentials
