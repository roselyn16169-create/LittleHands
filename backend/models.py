"""数据表结构（DDL）与种子数据。金额单位统一为「分」（INTEGER）。"""

DDL_SQL = """
-- ============ 家务项 ============
CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,                         -- 名称，如「扫地」
    pinyin      TEXT    NOT NULL,                         -- 带声调拼音，如「sǎo dì」
    icon        TEXT    NOT NULL DEFAULT '🧹',            -- emoji 图标，零图片资源
    price       INTEGER NOT NULL CHECK (price >= 0),      -- 单价（分）
    daily_limit INTEGER,                                  -- 每日打卡上限；NULL = 不限
    sort_order  INTEGER NOT NULL DEFAULT 0,               -- 显示顺序
    is_active   INTEGER NOT NULL DEFAULT 1,               -- 1=上架（儿童端可见）0=下架
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
);

-- ============ 打卡记录（含快照：改价/改名不影响历史）============
CREATE TABLE IF NOT EXISTS daily_records (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     INTEGER NOT NULL REFERENCES tasks(id),
    task_name   TEXT    NOT NULL,                         -- 快照：打卡时名称
    task_icon   TEXT    NOT NULL,                         -- 快照：打卡时图标
    price       INTEGER NOT NULL,                         -- 快照：打卡时单价（分）
    quantity    INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
    amount      INTEGER NOT NULL CHECK (amount = price * quantity),  -- 分
    record_date TEXT    NOT NULL,                         -- 'YYYY-MM-DD'
    created_at  TEXT    NOT NULL                          -- 实际提交时间
);

CREATE INDEX IF NOT EXISTS idx_records_task_date ON daily_records(task_id, record_date);
CREATE INDEX IF NOT EXISTS idx_records_date      ON daily_records(record_date);

-- ============ 家务变更日志（家长操作审计）============
CREATE TABLE IF NOT EXISTS task_logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id    INTEGER,                                   -- 不加外键：任务下架后日志仍保留
    task_name  TEXT    NOT NULL,
    action     TEXT    NOT NULL CHECK (action IN ('create', 'update', 'delete')),
    changes    TEXT    NOT NULL DEFAULT '[]',             -- JSON 字段级 diff
    operator   TEXT    NOT NULL DEFAULT 'parent',
    created_at TEXT    NOT NULL
);

-- ============ 轻量配置（存放家长 PIN 等）============
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- ============ 家长会话 token（单会话：每次解锁即作废旧 token）============
CREATE TABLE IF NOT EXISTS auth_tokens (
    token      TEXT PRIMARY KEY,
    expires_at REAL NOT NULL,                             -- 过期时间戳
    created_at TEXT NOT NULL
);

-- ============ 结算记录（余额 = 累计打卡收益 - 累计结算，转账线下完成仅记账）============
CREATE TABLE IF NOT EXISTS settlements (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    amount         INTEGER NOT NULL CHECK (amount > 0),   -- 分
    method         TEXT    NOT NULL,                      -- 支付宝/微信/现金/玩具兑换…
    note           TEXT,                                  -- 备注（如：买了乐高）
    balance_before INTEGER NOT NULL,                      -- 结算前余额（分）
    balance_after  INTEGER NOT NULL,                      -- 结算后余额（分）
    operator       TEXT    NOT NULL DEFAULT 'parent',
    created_at     TEXT    NOT NULL
);
"""

# 预置 8 项常见家务（price 单位：分；0.5 元 = 50）
# 默认不限每日次数（一天内可多次打卡），家长可在后台为单项设置上限
SEED_TASKS = [
    {"name": "扫地",     "pinyin": "sǎo dì",         "icon": "🧹", "price": 150, "daily_limit": None},
    {"name": "拖地",     "pinyin": "tuō dì",         "icon": "🪣", "price": 200, "daily_limit": None},
    {"name": "擦桌子",   "pinyin": "cā zhuō zi",     "icon": "🧽", "price": 50,  "daily_limit": None},
    {"name": "倒垃圾",   "pinyin": "dào lā jī",      "icon": "🗑️", "price": 50,  "daily_limit": None},
    {"name": "叠被子",   "pinyin": "dié bèi zi",     "icon": "🛏️", "price": 100, "daily_limit": None},
    {"name": "洗碗",     "pinyin": "xǐ wǎn",         "icon": "🍽️", "price": 300, "daily_limit": None},
    {"name": "收拾玩具", "pinyin": "shōu shi wán jù", "icon": "🧸", "price": 50,  "daily_limit": None},
    {"name": "洗衣服",   "pinyin": "xǐ yī fu",       "icon": "🧺", "price": 200,  "daily_limit": None},
]

# 默认配置
SEED_SETTINGS = {
    "pin": "1234",  # 家长后台 4 位 PIN
}
