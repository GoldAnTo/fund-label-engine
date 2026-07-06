# Fund Label Engine 容器化部署
# 多阶段构建：第一阶段构建前端，第二阶段只保留运行时所需的产物

# -------- 阶段 1：前端构建 --------
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# -------- 阶段 2：后端 + 前端产物整合 --------
FROM python:3.11-slim AS backend

# 系统依赖：curl 仅用于容器健康检查
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 复制 Python 项目描述并安装依赖
COPY pyproject.toml ./
COPY backend ./backend
COPY scripts ./scripts
COPY config ./config

RUN pip install --no-cache-dir -e ".[dev]" || pip install --no-cache-dir -e "."

# 复制前端构建产物（由阶段 1 构建）
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# 数据目录：用于存放运行时数据库和备份
RUN mkdir -p /app/data /app/backups
ENV FLE_OUTPUT_DB=/app/data/output.sqlite
ENV FLE_SOURCE_DB=/app/data/source.sqlite
ENV PYTHONPATH=/app/backend

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# 默认入口：启动 uvicorn 服务
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
