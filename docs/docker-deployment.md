# Docker 部署指南

## 快速开始

```bash
# 构建并启动
docker compose up --build -d

# 查看日志
docker compose logs -f app

# 健康检查
curl http://localhost:8000/health
# 期望返回 {"status":"ok"}

# 停止
docker compose down

# 清理数据（会删除数据库）
docker compose down -v
```

## 数据持久化

服务挂载了两个具名 volume：
- `fle-data`：运行时数据库（`output.sqlite`、`source.sqlite`）
- `fle-backups`：自动生成的备份

查看 volume：
```bash
docker volume ls | grep fle
```

把备份拷贝到主机：
```bash
docker run --rm -v fle-backups:/backups -v $(pwd):/out alpine \
    tar czf /out/backups.tgz -C /backups .
```

## 跑批

容器内 exec 跑一次 batch：
```bash
docker compose exec app python -m app.batch \
    --source-db /app/data/source.sqlite \
    --output-db /app/data/output.sqlite \
    --source funddata \
    --rule-config /app/config/rules.v1.json
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `PYTHONUNBUFFERED` | `1` | 实时输出日志（推荐生产） |
| `LOG_LEVEL` | `INFO` | JSON 日志的级别 |
| `FLE_NOTIFY_WEBHOOK_URL` | （空） | 配置后跑批失败会发 webhook 通知 |

## 构建产物大小优化

- 多阶段构建：前端在 `frontend-builder` 阶段构建，最终镜像不含 `node_modules`
- `--no-cache-dir`：避免 pip 缓存占用空间
- `.dockerignore`：排除 `.venv/`、`data/`、`.git/` 等

## 故障排查

1. **容器启动失败**
   ```bash
   docker compose logs app
   ```
   重点看 uvicorn 启动报错（多半是 DB 路径权限问题）

2. **数据库锁住**
   - SQLite 在高并发写入时可能锁定，建议生产改为 PostgreSQL
   - 本项目设计为单人研究环境，短期内 SQLite 足够

3. **健康检查失败**
   ```bash
   docker compose exec app curl -v http://localhost:8000/health
   ```
