# TRO Monitor

**English** | [中文](#中文)

Automated monitoring system for U.S. federal court Temporary Restraining Orders (TROs), helping Chinese cross-border e-commerce sellers identify IP-infringement risks in their supply chains.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Data Sources                         │
│         CourtListener API  ·  PACER / RECAP             │
└───────────────────────┬─────────────────────────────────┘
                        │ REST / scrape
┌───────────────────────▼─────────────────────────────────┐
│              Multimodal Processing                      │
│   APScheduler  ·  PDF text extraction  ·  OCR (Tesseract)│
│   Defendant name cleaning  ·  Risk scoring              │
└──────────┬───────────────────────────┬──────────────────┘
           │ MySQL                     │ MinIO
┌──────────▼──────────┐   ┌───────────▼──────────────────┐
│    Relational DB    │   │       Object Storage         │
│   cases · defendants│   │   Schedule A PDFs  ·  docs  │
│   risk_scores · docs│   └──────────────────────────────┘
└──────────┬──────────┘
           │ sync
┌──────────▼──────────────────────────────────────────────┐
│                  Elasticsearch                          │
│        Full-text search  ·  Fuzzy match  ·  Filters    │
└──────────┬──────────────────────────────────────────────┘
           │ HTTP
┌──────────▼──────────────────────────────────────────────┐
│                FastAPI Backend                          │
│   /login  ·  /search  ·  /cases  ·  /health            │
│   JWT auth  ·  Rate limiting  ·  Input validation       │
└──────────┬──────────────────────────────────────────────┘
           │ HTTP / proxy
┌──────────▼──────────────────────────────────────────────┐
│              React Frontend + Nginx                     │
│   Supplier search  ·  Risk badges  ·  Case cards       │
└─────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Data collection | Python · requests · APScheduler |
| PDF processing | pdfplumber · pdf2image · Tesseract OCR |
| Storage | MySQL 8 · MinIO (S3-compatible) |
| Search | Elasticsearch 8 · rapidfuzz |
| Backend | FastAPI · python-jose (JWT) · bcrypt |
| Frontend | React 18 · CSS custom properties |
| Infrastructure | Docker Compose · Nginx · healthcheck |
| Monitoring | UptimeRobot · internal health-check script |

---

## Project Structure

```
tro-collector/
├── collectors/          # CourtListener API client, PDF downloader, name cleaner
│   ├── courtlistener.py #   fetch cases with retry logic
│   ├── pdf_collector.py #   download PDFs → MinIO
│   ├── pdf_parser.py    #   text extraction + OCR
│   ├── cleaner.py       #   normalize defendant names
│   └── logger.py        #   shared logging (collector.log / error.log)
├── api/
│   └── main.py          # FastAPI: /login /search /cases /health
├── auth/
│   ├── jwt_handler.py   # create_token / verify_token (python-jose)
│   └── users.py         # bcrypt password verification
├── models/
│   └── database.py      # MySQL schema init, save_cases()
├── risk/
│   └── scorer.py        # risk score formula, company grouping (rapidfuzz)
├── search/
│   ├── es_client.py     # Elasticsearch index management, bulk index
│   └── sync.py          # MySQL → ES sync, mark es_synced
├── storage/
│   └── minio_client.py  # MinIO upload, presigned URL
├── alerts/
│   └── notifier.py      # daily new-case alerts, alert_log dedup
├── scripts/
│   └── health_check.py  # 4-point health check (DB / ES / disk / recency)
├── scheduler.py         # APScheduler daily job (02:00 UTC)
├── docker-compose.yml   # mysql · minio · elasticsearch · backend · scheduler · frontend · nginx
├── Dockerfile.backend
├── frontend/
│   ├── Dockerfile.frontend
│   └── src/
│       ├── App.js       # search UI, result cards, risk badges
│       └── App.css      # design tokens, card styles
└── nginx/
    └── nginx.conf       # /api/ → backend:8000, / → frontend:80
```

---

## Quick Start

**Prerequisites:** Docker, Docker Compose

```bash
# 1. Copy and fill in the config
cp .env.example .env

# 2. Start all services
docker compose up -d

# 3. Open in browser
open http://localhost
```

**Local development (without Docker)**

```bash
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000   # backend

cd frontend && npm install && npm start     # frontend (separate terminal)
```

---

## Monitoring

Configure [UptimeRobot](https://uptimerobot.com) (free tier) for uptime alerts:

1. Create a **HTTP(S)** monitor → URL: `http://your-domain/api/health`
2. Check interval: **5 minutes**
3. Alert contact: email

The built-in `scripts/health_check.py` runs after every daily job and writes to `logs/error.log` on:
- No new cases in the past 7 days
- ES sync backlog > 100 records
- Disk usage > 85 %
- No data collected in the past 48 hours

---

## Roadmap

| Phase | Status | Scope |
|-------|--------|-------|
| Phase 1 | ✅ Done | CourtListener collection · name cleaning · MySQL · FastAPI · React UI |
| Phase 2 | ✅ Done | APScheduler · logging · retry · PDF collection · MinIO · risk scoring · JWT · Docker |
| Phase 3 | 🔄 In progress | PACER / RECAP PDF parsing — Schedule A defendant extraction |
| Phase 4 | ⬜ Planned | Elasticsearch multi-dimension search |
| Phase 5 | ⬜ Planned | Alert push notifications (email / Slack / WeChat) |
| Phase 6 | ⬜ Planned | Cloud deployment (Alibaba Cloud / Tencent Cloud) · system monitoring |

---

---

# 中文

自动监测美国联邦法院 TRO（临时禁制令）案件，帮助跨境电商卖家提前排查供应商知识产权侵权风险。

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                      数据源                              │
│           CourtListener API  ·  PACER / RECAP            │
└───────────────────────┬─────────────────────────────────┘
                        │ REST / 抓取
┌───────────────────────▼─────────────────────────────────┐
│                   多模态处理层                            │
│   APScheduler定时  ·  PDF文本提取  ·  OCR（Tesseract）    │
│           被告名称清洗  ·  风险评分                       │
└──────────┬───────────────────────────┬──────────────────┘
           │ MySQL                     │ MinIO
┌──────────▼──────────┐   ┌───────────▼──────────────────┐
│      关系型数据库     │   │         对象存储              │
│ cases · defendants  │   │   Schedule A PDF · 文书附件  │
│ risk_scores · docs  │   └──────────────────────────────┘
└──────────┬──────────┘
           │ 同步
┌──────────▼──────────────────────────────────────────────┐
│                  Elasticsearch                          │
│           全文检索  ·  模糊匹配  ·  多维过滤             │
└──────────┬──────────────────────────────────────────────┘
           │ HTTP
┌──────────▼──────────────────────────────────────────────┐
│                  FastAPI 后端                            │
│   /login  ·  /search  ·  /cases  ·  /health            │
│          JWT鉴权  ·  限流  ·  输入校验                   │
└──────────┬──────────────────────────────────────────────┘
           │ HTTP / 反向代理
┌──────────▼──────────────────────────────────────────────┐
│              React 前端 + Nginx                          │
│         供应商搜索  ·  风险徽章  ·  案件卡片              │
└─────────────────────────────────────────────────────────┘
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 数据采集 | Python · requests · APScheduler |
| PDF 处理 | pdfplumber · pdf2image · Tesseract OCR |
| 存储 | MySQL 8 · MinIO（S3 兼容） |
| 搜索 | Elasticsearch 8 · rapidfuzz 模糊匹配 |
| 后端 | FastAPI · python-jose（JWT）· bcrypt |
| 前端 | React 18 · CSS 自定义属性 |
| 基础设施 | Docker Compose · Nginx · 健康检查 |
| 监控 | UptimeRobot · 内置健康检查脚本 |

## 快速启动

```bash
cp .env.example .env      # 填写真实配置
docker compose up -d       # 启动全部服务
open http://localhost       # 浏览器访问
```

**本地开发（不用 Docker）**

```bash
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000

cd frontend && npm install && npm start
```

## 实施进度

| 阶段 | 状态 | 内容 |
|------|------|------|
| 第一阶段 | ✅ 已完成 | CourtListener 采集 · 名称清洗 · MySQL · FastAPI · React 界面 |
| 第二阶段 | ✅ 已完成 | APScheduler · 日志 · 重试 · PDF采集 · MinIO · 风险评分 · JWT鉴权 · Docker部署 |
| 第三阶段 | 🔄 进行中 | PACER / RECAP PDF 解析 — Schedule A 被告名单提取 |
| 第四阶段 | ⬜ 计划中 | Elasticsearch 多维度搜索 |
| 第五阶段 | ⬜ 计划中 | 预警推送（邮件 / Slack / 企业微信） |
| 第六阶段 | ⬜ 计划中 | 云服务器部署（阿里云 / 腾讯云）· 系统监控 |
