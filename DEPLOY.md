# 二手车 MCP 服务器 Railway 部署指南

## 目录
- [快速部署](#快速部署)
- [详细步骤](#详细步骤)
- [环境变量配置](#环境变量配置)
- [GitHub 连接](#github-连接)
- [常见问题](#常见问题)

---

## 快速部署

### 前置要求
1. GitHub 账号
2. Railway 账号（免费注册：https://railway.app）

### 一键部署

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new)

1. 点击上方按钮跳转到 Railway
2. 选择 "Deploy from GitHub repo"
3. 选择包含 `二手车推荐skill/mcp/` 目录的仓库
4. Railway 会自动检测 Python 项目
5. 确认构建命令：`pip install -r requirements.txt`
6. 确认启动命令：`web: python run.py api`
7. 点击 "Deploy"

---

## 详细步骤

### 第一步：准备代码仓库

确保你的仓库包含以下文件结构：

```
your-repo/
└── 二手车推荐skill/
    └── mcp/
        ├── run.py           # 入口文件
        ├── api.py           # API 模块
        ├── server.py        # MCP Server
        ├── database.py     # 数据库模块
        ├── requirements.txt # 依赖列表
        ├── Procfile         # 启动命令
        ├── runtime.txt      # Python 版本
        └── railway.json     # Railway 配置
```

### 第二步：注册 Railway 账号

1. 访问 https://railway.app
2. 点击 "Sign Up" 使用 GitHub 账号登录
3. 授权 Railway 访问你的 GitHub 仓库

### 第三步：创建新项目

**方式 A：GUI 界面操作**
1. 在 Railway 控制台点击 "New Project"
2. 选择 "Deploy from GitHub repo"
3. 选择你的仓库和分支
4. 选择部署路径：`二手车推荐skill/mcp`
5. Railway 会自动检测为 Python 项目

**方式 B：使用 Railway CLI**
```bash
# 安装 Railway CLI
npm install -g @railway/cli

# 登录
railway login

# 进入项目目录
cd 二手车推荐skill/mcp

# 创建新项目
railway init

# 关联 GitHub 仓库
railway connect --github

# 部署
railway up
```

### 第四步：配置环境变量

在 Railway 项目设置中添加以下变量：

| 变量名 | 说明 | 示例值 |
|--------|------|--------|
| `PORT` | 服务端口（自动分配，无需手动设置） | Railway 自动设置 |
| `DATABASE_PATH` | 数据库文件路径 | `./data/cars.db` |
| `API_SECRET_KEY` | API 认证密钥 | `your-secret-key` |
| `ALLOWED_ORIGINS` | CORS 允许的域名 | `https://your-app.com` |

### 第五步：配置健康检查

Railway 会自动检查服务是否响应：

1. 进入项目 → Settings → Health Check
2. 设置检查路径：`/`
3. 超时时间：30 秒
4. 端口：`8000`（Railway 会通过 PORT 环境变量传递）

---

## 环境变量配置

### 必需变量

| 变量名 | 必填 | 说明 |
|--------|------|------|
| `PORT` | 否 | Railway 自动设置，代码中已处理 |

### 可选变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `DATABASE_PATH` | `./data/cars.db` | SQLite 数据库路径 |
| `API_SECRET_KEY` | 自动生成 | API 认证密钥 |
| `ALLOWED_ORIGINS` | `*` | CORS 允许的域名 |
| `LOG_LEVEL` | `INFO` | 日志级别 |

### Railway 环境变量设置步骤

1. 进入项目 Dashboard
2. 点击 "Variables" 标签
3. 点击 "New Variable" 添加变量
4. 支持从 .env 文件批量导入

---

## GitHub 连接

### 自动部署配置

1. 进入项目 Settings
2. 选择 "Git Sync"
3. 连接你的 GitHub 仓库
4. 设置自动部署的分支（推荐 `main`）
5. 启用 "Auto Deploy" 选项

### 工作流

```
开发者 Push → GitHub → Railway 自动部署
```

### 手动触发部署

```bash
railway up --prod
```

---

## 常见问题

### Q1: 部署失败，依赖安装超时

**解决方案：**
- 检查 `requirements.txt` 是否包含所有依赖
- 减少不必要的依赖
- 使用国内镜像源（在 `requirements.txt` 顶部添加）：
  ```
  -i https://pypi.tuna.tsinghua.edu.cn/simple
  ```

### Q2: 服务启动后立即崩溃

**检查项：**
1. 确认 `Procfile` 格式正确：`web: python run.py api`
2. 确认 `PORT` 环境变量可读取
3. 检查日志：进入项目 → Deployments → 查看最新日志

### Q3: 健康检查失败

**解决方案：**
- 确保 API 服务在端口响应 HTTP 请求
- 检查 `/docs` 端点是否可访问
- 调整健康检查超时时间

### Q4: 数据库文件丢失

**原因：** Railway 容器重启后文件系统会清空

**解决方案：**
- 使用 Railway 提供的持久化存储：
  1. 项目 Settings → Add Persistent Disk
  2. 挂载到 `./data` 目录
- 或使用云数据库（PostgreSQL/MySQL）

### Q5: 如何查看运行日志

**GUI：**
1. 进入项目 Dashboard
2. 点击 "Deployments"
3. 选择最近的部署
4. 查看实时日志

**CLI：**
```bash
railway logs
railway logs --tail 100
```

### Q6: 如何SSH到容器调试

```bash
railway ssh
```

---

## 部署检查清单

部署完成后，确认以下内容：

- [ ] 服务状态显示 "Deployed"
- [ ] 健康检查通过
- [ ] API 文档可访问：`https://your-project.railway.app/docs`
- [ ] 可以正常查询车源
- [ ] GitHub 推送后自动部署生效

---

## API 端点

部署成功后，可用的 API 端点：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 健康检查 |
| `/docs` | GET | API 文档（Swagger UI） |
| `/api/cars` | GET/POST | 车源查询/创建 |
| `/api/dealers` | GET/POST | 车商管理 |

---

## 扩展阅读

- [Railway 文档](https://docs.railway.app/)
- [Railway CLI 文档](https://docs.railway.app/cli)
- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [MCP 协议文档](https://modelcontextprotocol.io/)
