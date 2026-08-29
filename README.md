# TRO 监测系统

自动采集美国联邦法院 TRO（临时禁制令）案件，供跨境电商卖家查询供应商侵权风险。

## 快速启动

**前置条件：** Docker、Docker Compose

```bash
# 1. 复制配置文件并填入真实值
cp .env.example .env

# 2. 启动所有服务
docker compose up -d

# 3. 访问系统
open http://localhost
```

## 服务说明

| 服务 | 端口 | 说明 |
|------|------|------|
| nginx | 80 | 统一入口，反向代理 |
| frontend | 3000 | React 查询界面 |
| backend | 8000 | FastAPI 接口服务 |
| scheduler | — | 每日凌晨 2 点自动采集 |
| mysql | 3306 | 案件与被告数据存储 |
| elasticsearch | 9200 | 全文检索索引 |
| minio | 9000 / 9001 | PDF 文书对象存储 |

## 监控

使用 [UptimeRobot](https://uptimerobot.com) 免费监控服务可用性：

1. 注册 uptimerobot.com 免费账号
2. 新建 **HTTP(S)** 监控，URL 填 `http://你的域名/api/health`
3. 检查间隔设为 **5 分钟**
4. 通知方式选**邮件**，故障时自动报警

系统内置健康检查脚本（`scripts/health_check.py`），每日随采集任务运行，
异常写入 `logs/error.log`，检查项包括：
- 7 天内是否有新案件入库
- ES 待同步记录是否积压超过 100 条
- 磁盘使用率是否超过 85%
- 是否超过 48 小时未采集到新数据

## 开发说明

本地开发无需 Docker，直接运行：

```bash
pip install -r requirements.txt

# 启动 API 服务（热重载）
uvicorn api.main:app --reload --port 8000

# 启动前端（另开终端）
cd frontend && npm install && npm start
```

确保本地已启动 MySQL、Elasticsearch、MinIO，并正确配置 `.env`。
