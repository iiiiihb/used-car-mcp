# MCP 架构设计文档

> 二手车推荐系统 MCP 服务器架构设计

## 1. 概述

### 1.1 MCP 简介

MCP（Model Context Protocol，模型上下文协议）是由 Anthropic 于 2024 年 11 月提出的开放标准协议，旨在标准化 AI 应用与外部数据源、工具和系统之间的连接方式。

### 1.2 项目目标

- 为二手车推荐 skill 提供实时、准确的车源数据
- 支持车商自助上传和管理车源
- 实现多租户数据隔离
- 提供标准化的 API 接口供 AI 应用调用

## 2. 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        AI 应用层                                 │
│  ┌─────────────────┐    ┌─────────────────┐                   │
│  │  二手车推荐 Skill │    │  其他 AI 应用   │                   │
│  └────────┬────────┘    └────────┬────────┘                   │
│           │                      │                              │
│           └──────────┬───────────┘                              │
│                      │                                          │
│                      ▼                                          │
│         ┌──────────────────────┐                               │
│         │   MCP Client (SDK)    │                               │
│         └──────────┬─────────────┘                               │
└───────────────────│─────────────────────────────────────────────┘
                    │ JSON-RPC 2.0
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                      MCP 服务器层                                │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    MCP Server (FastMCP)                     │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │ │
│  │  │   Tools     │  │  Resources  │  │      Prompts        │ │ │
│  │  │  - 搜索车源  │  │ - 配置信息   │  │  - 搜索提示模板     │ │ │
│  │  │ - 匹配推荐  │  │ - 数据结构   │  │  - 对比提示模板     │ │ │
│  │  │ - 统计信息  │  │             │  │                     │ │ │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    REST API Server (FastAPI)                │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐  │ │
│  │  │ 车商注册  │  │  车源上传  │  │  车源管理  │  │   统计分析  │  │ │
│  │  │ POST     │  │  POST    │  │ GET/PUT  │  │   GET     │  │ │
│  │  │ /dealers │  │  /cars   │  │ /cars/id │  │   /stats  │  │ │
│  │  └──────────┘  └──────────┘  └──────────┘  └────────────┘  │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                      数据存储层                                  │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    SQLite Database                          │ │
│  │  ┌─────────────────┐  ┌─────────────────────────────────┐  │ │
│  │  │    dealers      │  │           cars                   │  │ │
│  │  │ ─────────────── │  │ ─────────────────────────────── │  │ │
│  │  │ dealer_id (PK) │  │ car_id (PK)                      │  │ │
│  │  │ dealer_name    │  │ dealer_id (FK)                   │  │ │
│  │  │ api_key        │  │ brand, series, model             │  │ │
│  │  │ api_secret     │  │ price, original_price            │  │ │
│  │  │ region, city   │  │ year, month, mileage             │  │ │
│  │  │ status         │  │ car_type, fuel_type              │  │ │
│  │  └─────────────────┘  │ region, city, condition         │  │ │
│  │                       │ status, tags, images            │  │ │
│  │                       └─────────────────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## 3. 数据库设计

### 3.1 车商表 (dealers)

| 字段 | 类型 | 说明 |
|------|------|------|
| dealer_id | TEXT (PK) | 车商唯一标识 |
| dealer_name | TEXT | 车商名称 |
| dealer_type | TEXT | 类型：personal/dealer/enterprise |
| api_key | TEXT (UNIQUE) | API 访问密钥 |
| api_secret | TEXT | API 签名密钥 |
| phone | TEXT | 联系电话 |
| email | TEXT | 电子邮箱 |
| region | TEXT | 所在省份 |
| city | TEXT | 所在城市 |
| address | TEXT | 详细地址 |
| rating | REAL | 评分 |
| status | TEXT | 状态：active/suspended/inactive |
| created_at | TEXT | 创建时间 |
| updated_at | TEXT | 更新时间 |

### 3.2 车源表 (cars)

| 字段 | 类型 | 说明 |
|------|------|------|
| car_id | TEXT (PK) | 车源唯一标识 |
| dealer_id | TEXT (FK) | 车商标识 |
| brand | TEXT | 品牌 |
| series | TEXT | 车系 |
| model | TEXT | 车型 |
| price | REAL | 价格（万元） |
| original_price | REAL | 新车指导价 |
| discount_rate | REAL | 折扣率 |
| year | INTEGER | 上牌年份 |
| month | INTEGER | 上牌月份 |
| mileage | REAL | 行驶里程（万公里） |
| car_type | TEXT | 车型分类 |
| seats | INTEGER | 座位数 |
| fuel_type | TEXT | 能源类型 |
| transmission | TEXT | 变速箱 |
| emission_standard | TEXT | 排放标准 |
| color | TEXT | 颜色 |
| region | TEXT | 所在省份 |
| city | TEXT | 所在城市 |
| address | TEXT | 详细地址 |
| condition | TEXT | 车况 |
| warranty | TEXT | 质保信息 |
| tags | TEXT | 标签（JSON数组） |
| images | TEXT | 图片URL列表（JSON数组） |
| source | TEXT | 数据来源 |
| status | TEXT | 状态：available/reserved/sold/expired |
| created_at | TEXT | 创建时间 |
| updated_at | TEXT | 更新时间 |

### 3.3 索引设计

```sql
CREATE INDEX idx_cars_dealer ON cars(dealer_id);
CREATE INDEX idx_cars_region ON cars(region);
CREATE INDEX idx_cars_city ON cars(city);
CREATE INDEX idx_cars_brand ON cars(brand);
CREATE INDEX idx_cars_price ON cars(price);
CREATE INDEX idx_cars_status ON cars(status);
CREATE INDEX idx_cars_car_type ON cars(car_type);
CREATE INDEX idx_cars_fuel_type ON cars(fuel_type);
```

## 4. MCP 工具设计

### 4.1 核心工具

| 工具名称 | 功能 | 参数 |
|---------|------|------|
| search_cars | 查询车源 | region, city, brand, car_type, fuel_type, price_min, price_max, year_min, limit |
| get_car_detail | 获取车源详情 | car_id |
| match_cars_for_user | 智能匹配推荐 | budget_min, budget_max, preferred_brands, preferred_types, region, city, need_loan, limit |
| get_car_statistics_summary | 统计概览 | 无 |
| get_brands_and_types | 获取可选列表 | 无 |
| get_price_range | 价格区间参考 | brand |
| batch_import_cars_from_json | 批量导入 | cars_json |

### 4.2 资源定义

| 资源 URI | 说明 |
|---------|------|
| config://app_info | 应用配置信息 |
| schema://car | 车源数据结构定义 |

### 4.3 提示模板

| 模板名称 | 用途 |
|---------|------|
| car_search_prompt | 二手车搜索提示 |
| car_comparison_prompt | 车辆对比提示 |

## 5. REST API 设计

### 5.1 认证方式

使用 API Key 认证。车商注册后获得 api_key，后续所有请求通过 Header 传递：

```
X-Api-Key: your_api_key_here
```

### 5.2 API 端点

#### 车商管理

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | /api/v1/dealers/register | 注册车商 |
| GET | /api/v1/dealers/me | 获取我的信息 |

#### 车源管理

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | /api/v1/cars | 创建单个车源 |
| POST | /api/v1/cars/upload | Excel批量上传 |
| GET | /api/v1/cars | 查询车源列表 |
| GET | /api/v1/cars/{car_id} | 获取车源详情 |
| PUT | /api/v1/cars/{car_id} | 更新车源 |
| DELETE | /api/v1/cars/{car_id} | 删除车源（软删除） |

#### 统计分析

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | /api/v1/stats/my | 获取我的车源统计 |

## 6. 匹配算法

### 6.1 评分体系（0-100分）

```
总评分 = 预算匹配(0-40) + 品牌匹配(0-20) + 车型匹配(0-15) + 地区匹配(0-15) + 车况加分(0-10)
```

### 6.2 预算匹配规则

| 情况 | 分数 |
|------|------|
| 完全在预算内（最佳区间） | 40分 |
| 在预算内 | 35分 |
| 低于预算 ≤20% | 30分 |
| 低于预算 20-50% | 20分 |
| 超出预算 ≤10% | 25分 |
| 超出预算 10-20% | 15分 |
| 超出预算 20-30% | 5分 |
| 超出预算 >30% | 0分 |

### 6.3 贷款估算

- 默认首付比例：30%
- 默认贷款年限：3年
- 利率参考：4.75%（银行基准）
- 计算方式：等额本息

## 7. 部署架构

### 7.1 运行模式

1. **MCP Server 模式**（主要）
   - 通过 stdio 传输与 AI 应用通信
   - 适用于 Coze 等 AI 平台

2. **HTTP Server 模式**（辅助）
   - 通过 FastAPI 提供 REST API
   - 适用于车商上传管理

### 7.2 启动方式

```bash
# MCP Server 模式
python server.py stdio

# HTTP API 模式
python -m uvicorn api:app --host 0.0.0.0 --port 8000

# 或者直接运行（自动选择）
python server.py
```

### 7.3 配置文件

```yaml
# config.yaml
database:
  path: "./data/car_inventory.db"

server:
  name: "used-car-mcp"
  version: "1.0.0"

api:
  host: "0.0.0.0"
  port: 8000
  cors_origins:
    - "*"
```

## 8. 安全考虑

### 8.1 认证与授权

- API Key 长度 ≥ 32 字符
- API Secret 用于签名验证
- 数据按 dealer_id 隔离

### 8.2 输入验证

- 所有输入参数进行类型和范围校验
- SQL 注入防护（使用参数化查询）
- 文件上传格式和大小限制

### 8.3 速率限制

- 建议在生产环境添加 API 限流
- 默认每分钟 60 次请求

## 9. 后续扩展

### 9.1 短期扩展

- [ ] 添加图片上传和管理功能
- [ ] 实现车源状态流转（available → reserved → sold）
- [ ] 添加车源刷新/置顶功能

### 9.2 中期扩展

- [ ] 支持更多数据源（瓜子、人人车 API）
- [ ] 添加数据分析功能
- [ ] 实现团购功能

### 9.3 长期扩展

- [ ] 多数据库支持（PostgreSQL/MySQL）
- [ ] 分布式部署
- [ ] 实时数据同步
