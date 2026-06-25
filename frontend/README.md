# Fund Label Workbench (frontend)

Vite + React + TypeScript 工作台，对接 [backend](../backend) 暴露的 v1 API。

## 两种部署模式

### 1. 开发模式（前后端分别起服务）

```bash
# 1) 后端
cd ../
. .venv/bin/activate
FLE_DB_PATH=/path/to/label_results.sqlite \
  python -m uvicorn app.main:app --port 8765

# 2) 前端
cd frontend
npm install
npm run dev   # → http://localhost:5173
```

Vite dev server 把 `/v1` 和 `/health` 代理到 `http://localhost:8765`，前端调 API 走相对路径，无 CORS 问题。代理目标可用 `VITE_DEV_PROXY_TARGET` 覆盖。

### 2. 单进程模式（推荐演示/部署）

先打包前端，然后让 FastAPI 直接托管静态资源：

```bash
cd frontend && npm install && npm run build
cd ../
. .venv/bin/activate
FLE_DB_PATH=/path/to/label_results.sqlite \
  python -m uvicorn app.main:app --port 8765
```

打开 http://localhost:8765，前后端共用一个端口。`backend/app/main.py` 会自动探测仓库根的 `frontend/dist`；用 `FLE_FRONTEND_DIST=/some/path/dist` 可显式指定。

## 页面

- `/runs`：批次列表 + 触发新批次
- `/runs/:runId`：批次详情 + 基金列表
- `/runs/:runId/funds/:fundCode`：完整 Fund Report（标签 / 证据 / 特征 / 复核历史 / 提交复核）
- `/search`：基金检索（按 fund_code 模糊、按标签、按复核动作）
- `/review-queue`：仅列 manual_review 的基金
