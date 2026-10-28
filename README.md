# 🖐️ LittleHands 小手家务

> v1.0.0 · 小手也能做大事——引导 6-12 岁儿童做家务、赚积分、攒小金库的本地家庭应用

## ✨ 功能亮点

- 🧒 **儿童打卡页**：大字号 + emoji 图标 + 带声调拼音；点卡片即打卡（一次勾选 = 1 次，同一家务一天内可在不同时间多次打卡，默认不限次数），卡片左上角显示今日完成次数；顶部实时金额、一键提交、`+X 元 🎉` 即时奖励动效；家长设置了每日上限的家务打满后自动置灰
- 🐷 **小金库**：累计 / 本月 / 今日收益、打卡天数、今日明细（按家务聚合显示次数）、按月浏览每日记录、点开回看当日明细
- 💰 **结算记账**：家长选择方式（支付宝/微信/现金/玩具兑换…）记录结算金额，余额自动重算 = 累计收益 − 已结算；转账线下完成仅记账，支持撤销，孩子端同步可见「当前余额 + 兑换记录」- 🔒 **家长后台**（4 位 PIN 锁屏 + 防乱试锁定）：家务增删改查（emoji 图标选择器、拼音留空自动生成、每日上限、排序）、字段级**变更日志**、收益概览与**近 7 天趋势图**、修改 PIN
- 🏅 **成就徽章**：12 枚游戏化勋章（坚持之星/勤劳天数/单项能手/多面手/小富翁/兑换系列），打卡与结算实时判定，解锁弹出动效，小金库成就墙展示进度
- 📱 **响应式**：手机 2 列 / 平板 3 列 / iPad 横屏与 PC 4 列；触控目标大、防双击缩放、适配全面屏安全区；支持 Safari「添加到主屏幕」获得类 App 体验
- 💾 **纯本地**：SQLite 单文件数据库，零云依赖、零隐私顾虑、数据可随时备份

## 🧰 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.10+ · FastAPI · SQLite（标准库 sqlite3，无 ORM、无迁移工具） |
| 前端 | 原生 HTML / CSS / JavaScript（ES Modules）· Tailwind CSS（CDN） |
| 测试 | 标准库 urllib 接口回归测试，62 项断言一键运行（详见 docs/TEST_PLAN.md） |

## 🚀 快速开始

```bash
git clone https://github.com/roselyn16169-create/LittleHands.git
cd LittleHands/backend
python3 -m venv ../.venv
../.venv/bin/pip install -r requirements.txt
../.venv/bin/uvicorn main:app --reload --port 8000
```

| 入口 | 地址 |
|---|---|
| 儿童打卡页 | http://127.0.0.1:8000 |
| 家长后台 | http://127.0.0.1:8000/admin.html （默认 PIN `1234`，**请尽快修改**） |
| 交互式接口文档 | http://127.0.0.1:8000/docs |

首次启动自动建库，并预置 8 项常见家务（默认不限每日次数，家长可在后台为单项设置上限）：🧹扫地 · 🪣拖地 · 🧽擦桌子 · 🗑️倒垃圾 · 🛏️叠被子 · 🍽️洗碗 · 🧸收拾玩具 · 🧺洗衣服。

> 💡 **全家共用**：iPad 浏览器访问 `http://<电脑IP>:8000` 即可；在 Safari「分享 → 添加到主屏幕」可获得全屏体验。
> ⚠️ 样式通过 Tailwind CDN 加载，首次打开需能访问外网（如需完全离线，可自行把 CDN 脚本下载至本地引用）。

## 📁 项目结构

```
LittleHands/
├── backend/
│   ├── main.py               # FastAPI 入口：路由挂载 + 静态托管
│   ├── database.py           # SQLite 连接/事务/建表/种子
│   ├── models.py             # 表结构 DDL 与种子数据
│   ├── schemas.py            # Pydantic 请求模型
│   ├── auth.py               # PIN 校验（SHA-256）/ token / 防乱试
│   ├── utils.py              # 金额分↔元 / 时间 / pypinyin
│   ├── routers/
│   │   ├── tasks.py          # 儿童端：家务列表
│   │   ├── records.py        # 儿童端：打卡/明细/历史/汇总
│   │   └── admin.py          # 家长端：鉴权/CRUD/日志/统计
│   └── tests/                # 回归测试（run_tests.sh 一键运行）
├── frontend/
│   ├── index.html            # 儿童端（打卡 + 小金库）
│   ├── admin.html            # 家长后台（PIN 锁屏）
│   ├── css/style.css         # 动效与触控优化
│   └── js/                   # api / common / child / bank / admin
└── data/chore.db             # SQLite 数据文件（自动生成，不入库）
```

## 🔌 接口一览

| 分组 | 端点 |
|---|---|
| 儿童端 | `GET /api/tasks` · `GET /api/records/today` · `POST /api/records/submit` · `GET /api/records?date=` · `GET /api/records/history?month=` · `GET /api/records/summary` |
| 鉴权 | `POST /api/auth/verify` · `POST /api/auth/logout` · `PUT /api/auth/pin` |
| 儿童端·结算/成就 | `GET /api/settlements` · `GET /api/achievements` |
| 家长端 | `GET/POST /api/admin/tasks` · `PUT/DELETE /api/admin/tasks/{id}` · `GET /api/admin/logs` · `GET /api/admin/stats` · `GET/POST /api/admin/settlements` · `DELETE /api/admin/settlements/{id}` |

详细参数见 `/docs`（Swagger UI，支持在线调试）。

## 🧠 设计要点

- **金额一律存「分」**（INTEGER），杜绝浮点误差，接口层统一换算为元
- **打卡记录快照**：保存打卡时的名称/图标/单价，日后改价改名不影响历史
- **下架而非删除**：任务软删除 + 日志免外键约束，历史数据永久可追溯
- **提交全有或全无**：任一项超额整单拒绝并回滚，杜绝「半单」
- **PIN 安全**：SHA-256 存储（兼容旧明文自动升级）、连错 5 次锁定 30 秒、token 仅存内存（重启即失效）
- **幂等种子**：种子数据仅在空库写入，绝不覆盖家长的自定义内容
- **余额即派生**：余额 = 累计打卡收益 − 累计结算（settlements 仅记账，转账线下完成），撤销即返还
- **家长后台单会话**：每次进入后台均需输 PIN，token 仅存当前页面内存，返回儿童端即失效
## 🧪 运行测试

```bash
bash backend/tests/run_tests.sh
```

自动备份现有数据库 → 重置测试库 → 四阶段共 62 项断言 → 恢复原库。

## ❓ 常见问题

**忘记 PIN 怎么办？**
```bash
sqlite3 data/chore.db "DELETE FROM settings WHERE key='pin'"
```
重启服务即恢复默认 `1234`。

**如何备份数据？** 直接复制 `data/chore.db` 文件；恢复时放回原位置即可。

**想用独立测试库，不碰正式数据？**
```bash
CHORE_DB=/tmp/test.db ../.venv/bin/uvicorn main:app --port 8001
```

## 📄 许可证

[MIT](./LICENSE)
