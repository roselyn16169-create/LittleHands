# 🧹 家务小助手 chore-helper

引导 6-12 岁儿童做家务、赚积分、攒小金库的本地家庭应用。
技术栈：FastAPI + SQLite + 原生 HTML/Tailwind/JS，适配 iPad 与 PC。

## 快速开始

```bash
cd backend
python3 -m venv ../.venv
../.venv/bin/pip install -r requirements.txt
../.venv/bin/uvicorn main:app --reload --port 8000
```

打开 http://127.0.0.1:8000 （儿童端页面第 4 步开发中；接口文档见 /docs）

## 接口回归测试

```bash
bash backend/tests/run_tests.sh
```

自动备份现有数据库 → 重置测试库 → 依次运行儿童端/家长端共 32 项接口断言 → 恢复原数据库。

## 开发路线图

- [x] 第 1 步：后端骨架 + 建库 + 种子数据
- [x] 第 2 步：儿童端 API（打卡/明细/汇总）
- [x] 第 3 步：家长端 API（PIN 鉴权/任务 CRUD/变更日志）
- [x] 第 4 步：儿童打卡页
- [x] 第 5 步：小金库页
- [x] 第 6 步：家长后台页面
- [ ] 第 7 步：iPad 适配与体验打磨

## 设计要点

- 金额一律存「分」（INTEGER），杜绝浮点误差；接口层统一换算为元
- 打卡记录保存名称/图标/单价快照，历史不受后续修改影响
- 任务删除采用「下架」软删除，保证历史可追溯
- 家长 PIN 以 SHA-256 存储；token 仅存内存（重启即失效，家用足够）
- 打卡提交为「全有或全无」：任一项超额则整单拒绝
