# HANDOFF — TRO Monitor 项目交接文档

> 最后更新：2026-09-01  
> 分支：`main`（已从 `claude/tro-logging-system-1hxjjf` 合并）

---

## 一、项目是什么

自动监测美国联邦法院 TRO（临时禁制令）案件，帮助跨境电商卖家查询供应商知识产权侵权风险。

**技术栈：** CourtListener API → Python 采集 → MySQL + MinIO → Elasticsearch → FastAPI → React

---

## 二、已完成的工作

| 阶段 | 内容 | 状态 |
|------|------|------|
| Phase 1 | CourtListener 采集、名称清洗、MySQL 存储、FastAPI `/search` `/cases`、React 查询界面 | ✅ |
| Phase 2 | APScheduler 定时任务（每日 02:00）、日志系统（collector.log / error.log）、HTTP 重试（429/5xx/4xx 分类处理） | ✅ |
| Phase 3 | MinIO 对象存储、从 CourtListener 下载 PDF、Schedule A 解析（pdfplumber 文本 + Tesseract OCR） | ✅ |
| Phase 4 | Elasticsearch 索引、MySQL → ES 同步、`/search` 升级为 ES 优先 + MySQL 兜底 | ✅ |
| Phase 5 | 风险评分（数量/时间/类型/平台维度）、每日预警（alert_log 去重） | ✅ |
| Phase 6 | JWT 鉴权（python-jose + bcrypt）、限流（60次/60秒/IP）、Query 参数校验、全局 422 处理 | ✅ |
| Phase 7 | Docker Compose（7 服务）、健康检查脚本（4项）、双语 README | ✅ |

---

## 三、未完成 / 计划中

| 优先级 | 内容 | 说明 |
|--------|------|------|
| 高 | PACER/RECAP PDF 完整解析 | Schedule A 被告名单提取逻辑还较粗糙，OCR 准确率待验证 |
| 中 | 前端加 JWT 登录流程 | 目前 `/search` `/cases` 的 `get_current_user` 已注释掉方便本地调试，上生产前要恢复 |
| 中 | 限流恢复 | `check_rate_limit` 同样已注释掉，上生产前要恢复 |
| 中 | 预警推送渠道 | 目前只写 logger.warning，没有真实的邮件/Slack/企业微信发送 |
| 低 | 云服务器部署 | Docker Compose 已就绪，待选定云厂商（阿里云/腾讯云）后部署 |
| 低 | Elasticsearch 未在本地运行 | 本地搜索走 MySQL 兜底，ES 功能未实测 |

---

## 四、关键决策与原因

### 4.1 ES 失败时 fallback 到 MySQL
ES 连不上（本地未启动、云上未部署）时搜索不应直接 500。代码在 `api/main.py` 的 `search()` 里先 try ES，catch 任意异常后走 `_search_mysql()`，前端无感知。

### 4.2 passlib 换成直接调用 bcrypt
`passlib[bcrypt]` 与系统自带 `bcrypt` 包版本冲突（`bcrypt` 4.x 移除了 `__about__` 属性），直接 `import bcrypt` 调用 `hashpw` / `checkpw` 绕过冲突。`requirements.txt` 里是 `bcrypt`，不是 `passlib[bcrypt]`。

### 4.3 MySQL fallback 查询要 JOIN risk_scores
早期 MySQL fallback 没有 JOIN `risk_scores` 表，导致前端卡片风险徽章永远不显示。已在 `_search_mysql()` 里加 `LEFT JOIN risk_scores rs ON rs.company_name = d.cleaned_name`。

### 4.4 index.js 用 React 18 createRoot
create-react-app 18 默认生成 `createRoot`，但项目里的 index.js 最初是 React 17 的 `ReactDOM.render`，在 React 18 下会报 deprecation warning。已更新为 `createRoot`。

### 4.5 本地开发关闭 JWT 和限流
`get_current_user` 和 `check_rate_limit` 都已在 `/search` `/cases` 里注释掉（带 `# TODO: re-enable in production` 标记）。**上生产前必须取消注释。**

---

## 五、重要文件清单

| 文件 | 作用 | 注意点 |
|------|------|--------|
| `api/main.py` | FastAPI 主入口，所有路由 | JWT 和限流已注释，上线前恢复 |
| `auth/jwt_handler.py` | JWT 签发/校验，读 `JWT_SECRET_KEY` env | 默认 secret 是 `change-me-in-production`，生产必须改 |
| `auth/users.py` | 用户表，密码从 `ADMIN_PASSWORD` env 读取并 bcrypt | 每次启动重新 hash，不持久化到 DB |
| `collectors/courtlistener.py` | CourtListener API 采集 + 重试逻辑 | 429 按 Retry-After 等待，5xx 指数退避 |
| `collectors/logger.py` | 日志配置，ERROR+ 同时写 error.log | 所有模块共享这一个 logger 文件 |
| `models/database.py` | MySQL 建表 + save_cases() | `CREATE TABLE IF NOT EXISTS` 不会 ALTER 已有表（见坑 #1）|
| `risk/scorer.py` | 风险评分 + rapidfuzz 公司聚合 | 阈值 85，可调整 |
| `search/sync.py` | MySQL → ES 批量同步 | 只有整批成功才 mark es_synced=1 |
| `scheduler.py` | 定时任务主体，每日 02:00 UTC | PDF 采集失败不影响主流程（独立 try） |
| `scripts/health_check.py` | 4 项健康检查，写 error.log | 每日随 scheduler 运行 |
| `docker-compose.yml` | 7 服务完整部署 | backend 和 scheduler 共用同一个 Dockerfile |
| `.env.example` | 所有环境变量模板 | 本地复制为 `.env` 后填写真实值 |

---

## 六、当前已知问题

1. **本地 MySQL 表结构与代码不同步**  
   `init_db()` 只会 `CREATE TABLE IF NOT EXISTS`，不会 ALTER 已有表。如果数据库是在旧版本代码下建的，缺少 `docket_id`、`created_at`、`platform`、`es_synced` 等字段，搜索会报 `Unknown column` 错误。  
   → **解决**：手动执行 ALTER（见下方坑 #1）。

2. **Elasticsearch 本地未运行**  
   每次搜索都会先尝试连 ES（localhost:9200），失败后 fallback MySQL，终端会输出 ERROR 日志，但搜索结果正常。不影响使用，只是有噪音日志。

3. **风险分本地为空**  
   `risk_scores` 表只有运行 `update_risk_scores()`（在 `scheduler.py` 里）才会填充。直接启动 uvicorn 不会触发评分，搜索结果的风险徽章不显示。  
   → 运行一次 `python3 scheduler.py` 或单独调用 `from risk.scorer import update_risk_scores; update_risk_scores()`。

4. **预警只写日志，没有真实推送**  
   `alerts/notifier.py` 的 `send_alert()` 只调用 `logger.warning`，不发邮件/消息。

---

## 七、踩过的坑（后续不要重复）

### 坑 #1：init_db() 不会 ALTER 已有表
**现象：** 搜索报 `Table 'tro_db.documents' doesn't exist` 或 `Unknown column 'docket_id'`。  
**原因：** `CREATE TABLE IF NOT EXISTS` 在表已存在时直接跳过，新增字段不会生效。  
**修复：** 需要手动执行 ALTER TABLE：
```sql
ALTER TABLE cases
  ADD COLUMN docket_id INT AFTER id,
  ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP AFTER docket_number;

ALTER TABLE defendants
  ADD COLUMN platform VARCHAR(100) AFTER cleaned_name,
  ADD COLUMN source_doc_id INT AFTER platform,
  ADD COLUMN es_synced TINYINT DEFAULT 0 AFTER source_doc_id;
```

### 坑 #2：passlib 与系统 bcrypt 版本冲突
**现象：** 启动时报 `ValueError: password cannot be longer than 72 bytes` 或 `AttributeError: module 'bcrypt' has no attribute '__about__'`。  
**原因：** `passlib` 依赖 `bcrypt` 旧版 API，`bcrypt` 4.x 已移除。  
**修复：** 直接用 `import bcrypt`，不用 passlib。`requirements.txt` 里写 `bcrypt`。

### 坑 #3：frontend/ 被 git 识别为 gitlink（submodule）
**现象：** `git status` 显示 `frontend` mode 160000，push 后 GitHub 上 frontend 目录显示为灰色链接。  
**原因：** create-react-app 在 frontend/ 里自己初始化了 `.git`，导致父仓库将其识别为 submodule。  
**修复：** `git rm --cached frontend -f`，删除 `frontend/.git`，再重新 `git add frontend/`。

### 坑 #4：MySQL fallback 搜索结果无风险分
**现象：** 搜索有结果但卡片上风险徽章不显示。  
**原因：** `_search_mysql()` 没有 JOIN `risk_scores` 表。  
**修复：** 已加 `LEFT JOIN risk_scores rs ON rs.company_name = d.cleaned_name`，同时加了 `ORDER BY c.date_filed DESC`。

### 坑 #5：本地限速触发 429
**现象：** 刷新几次后前端返回 429 "请求过于频繁"。  
**原因：** `RateLimiter` 默认 60次/60秒，本地调试很容易触发。  
**修复：** 本地开发时注释掉 `/search` 和 `/cases` 里的 `Depends(check_rate_limit)`。

### 坑 #6：tro-collector 目录不是 git 仓库
**现象：** `git pull` 报 `fatal: not a git repository`。  
**原因：** 从 GitHub 下载的是 ZIP 压缩包，解压后没有 `.git` 目录。  
**修复：** 用 `git clone` 重新克隆，或用 `curl` 单独下载需要更新的文件。

### 坑 #7：MySQL root 用户有密码但 .env 里 DB_PASSWORD 留空
**现象：** 后端启动后搜索报 `Access denied for user 'root'@'localhost' (using password: NO)`。  
**修复：** 在 `.env` 里填写真实的 `DB_PASSWORD`，然后重启 uvicorn。

### 坑 #8：Playwright 截图因代理阻塞挂起
**现象：** `page.goto()` 等待 `networkidle` 超时，因为 Chromium 尝试连接 Google 服务被代理拦截。  
**规律：** 远端环境里跑 Playwright 时不要用 `networkidle`，改用 `domcontentloaded`；或直接让用户在本地打开浏览器截图，远端环境不适合截图验证 UI。

---

## 八、接下来要做什么

按优先级排序：

1. **本地完整跑通**：运行 `python3 scheduler.py` 触发完整 daily_job（采集→评分→预警），验证搜索有数据且风险分显示正常。

2. **恢复 JWT + 限流**：取消 `api/main.py` 里的注释，前端加登录页（POST /login → 存 token → 请求时带 Authorization 头）。

3. **预警推送实现**：在 `alerts/notifier.py` 的 `send_alert()` 里接入真实渠道（推荐企业微信 Webhook，最简单）。

4. **云服务器部署**：`docker compose up -d`，配置域名 + SSL，开启 UptimeRobot 监控 `/api/health`。

5. **ES 实测**：在有 Elasticsearch 的环境（Docker 或云上）验证全文搜索和模糊匹配效果。
