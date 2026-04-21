# 二手车 MCP 服务器

基于 Model Context Protocol (MCP) 的二手车车源查询服务。

## 功能特性

- 🔍 **车源查询** - 支持多条件筛选查询二手车
- 📊 **统计分析** - 提供品牌、价格等多维度统计
- 🔐 **API 认证** - 支持车商 API Key 认证
- 📄 **Excel 导入** - 支持 Excel 批量导入车源
- 🌐 **HTTP API** - 提供 RESTful API 接口

## 快速开始

### 本地运行

```bash
# 安装依赖
pip install -r requirements.txt

# 启动 API 服务
python run.py api

# 或启动 MCP Server（用于 AI 应用集成）
python run.py mcp
```

### Railway 部署

详细部署指南请查看 [DEPLOY.md](DEPLOY.md)

## API 文档

启动服务后访问：`http://localhost:8000/docs`

## 技术栈

- FastAPI - Web 框架
- FastMCP - MCP 协议实现
- SQLAlchemy - 数据库 ORM
- Pydantic - 数据验证
