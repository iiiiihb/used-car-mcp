# 车商上传接口文档

> 二手车 MCP 服务器 - 车商接入指南

## 目录

1. [快速开始](#1-快速开始)
2. [车商注册](#2-车商注册)
3. [车源上传](#3-车源上传)
4. [Excel 模板说明](#4-excel-模板说明)
5. [API 接口详解](#5-api-接口详解)
6. [错误处理](#6-错误处理)
7. [示例代码](#7-示例代码)

---

## 1. 快速开始

### 1.1 环境要求

- Python 3.10+
- 依赖安装：
```bash
cd ./二手车推荐skill/mcp
pip install -r requirements.txt
```

### 1.2 启动服务

```bash
# 启动 HTTP API 服务
python -m uvicorn api:app --host 0.0.0.0 --port 8000

# 或者使用默认方式
python api.py
```

服务启动后访问 `http://localhost:8000/docs` 查看 API 文档。

---

## 2. 车商注册

### 2.1 注册接口

```
POST /api/v1/dealers/register
```

#### 请求示例

```bash
curl -X POST "http://localhost:8000/api/v1/dealers/register" \
  -H "Content-Type: application/json" \
  -d '{
    "dealer_name": "上海优信二手车行",
    "dealer_type": "dealer",
    "phone": "13800138000",
    "email": "dealer@example.com",
    "region": "上海",
    "city": "上海市"
  }'
```

#### 响应示例

```json
{
  "dealer_id": "DEALER_20250520123456",
  "dealer_name": "上海优信二手车行",
  "api_key": "abc123...xyz789",
  "api_secret": "secret_xxx",
  "region": "上海",
  "status": "active"
}
```

⚠️ **重要**: 请妥善保存 `api_key` 和 `api_secret`，`api_secret` 仅在注册时返回一次。

### 2.2 后续请求认证

所有后续请求需要在 Header 中携带 API Key：

```
X-Api-Key: your_api_key_here
```

---

## 3. 车源上传

### 3.1 方式一：Excel 批量上传（推荐）

适用于车源较多的情况，支持 .xlsx, .xls, .csv 格式。

```bash
curl -X POST "http://localhost:8000/api/v1/cars/upload" \
  -H "X-Api-Key: your_api_key_here" \
  -F "file=@/path/to/cars.xlsx"
```

#### 响应示例

```json
{
  "message": "导入完成",
  "total": 100,
  "success_count": 98,
  "error_count": 2,
  "errors": [
    {
      "car_id": null,
      "error": "品牌字段不能为空"
    }
  ]
}
```

### 3.2 方式二：单个创建（API）

适用于添加单个车源或测试。

```bash
curl -X POST "http://localhost:8000/api/v1/cars" \
  -H "X-Api-Key: your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "brand": "比亚迪",
    "series": "宋Plus",
    "model": "宋Plus EV 2024款 冠军版 605KM",
    "price": 14.5,
    "original_price": 18.0,
    "year": 2024,
    "month": 3,
    "mileage": 1.2,
    "car_type": "SUV",
    "seats": 5,
    "fuel_type": "纯电动",
    "region": "上海",
    "city": "上海市",
    "condition": "原版原漆",
    "tags": ["准新车", "新能源", "续航500+"]
  }'
```

### 3.3 方式三：批量创建（JSON）

适用于程序化导入。

```bash
curl -X POST "http://localhost:8000/api/v1/cars/batch" \
  -H "X-Api-Key: your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "cars": [
      {
        "brand": "比亚迪",
        "model": "秦Plus",
        "price": 9.8,
        "year": 2023
      },
      {
        "brand": "特斯拉",
        "model": "Model 3",
        "price": 22.0,
        "year": 2024
      }
    ]
  }'
```

---

## 4. Excel 模板说明

### 4.1 模板下载

建议使用以下列名的 Excel 文件：

| 列名 | 字段 | 必填 | 说明 | 示例 |
|------|------|------|------|------|
| 品牌 | brand | ✅ | 汽车品牌 | 比亚迪 |
| 车系 | series | ❌ | 具体车系 | 宋Plus |
| 车型 | model | ✅ | 完整车型名 | 宋Plus EV 2024款 |
| 价格 | price | ✅ | 售价（万元） | 14.5 |
| 新车价 | original_price | ❌ | 指导价（万元） | 18.0 |
| 年份 | year | ❌ | 上牌年份 | 2024 |
| 月份 | month | ❌ | 上牌月份 | 3 |
| 里程 | mileage | ❌ | 行驶里程（万公里） | 1.2 |
| 车型分类 | car_type | ❌ | 大类 | SUV |
| 座位数 | seats | ❌ | 座位 | 5 |
| 能源类型 | fuel_type | ❌ | 动力类型 | 纯电动 |
| 变速箱 | transmission | ❌ | 变速方式 | 自动 |
| 排放标准 | emission_standard | ❌ | 环保等级 | 国六B |
| 颜色 | color | ❌ | 车身色 | 白色 |
| 省份 | region | ❌ | 所在地省 | 上海 |
| 城市 | city | ❌ | 所在地市 | 上海市 |
| 地址 | address | ❌ | 详细地址 | 浦东新区xxx |
| 车况 | condition | ❌ | 车况描述 | 原版原漆 |
| 质保 | warranty | ❌ | 质保期限 | 1年2万公里 |
| 标签 | tags | ❌ | 逗号分隔 | 准新车,性价比 |

### 4.2 枚举值说明

| 字段 | 可选值 |
|------|--------|
| 车型分类 | 轿车、SUV、MPV、跑车、皮卡、面包车、其他 |
| 能源类型 | 汽油、柴油、纯电动、插电混动、油电混动、增程式 |
| 变速箱 | 手动、自动、无级变速 |
| 排放标准 | 国五、国六、国六B、新能源 |
| 车况 | 原版原漆、轻微剐蹭、有过维修、事故车 |

### 4.3 示例 Excel

```
| 品牌   | 车系    | 车型                           | 价格  | 年份 | 里程 | 车型分类 | 省份 | 城市    | 车况     | 标签         |
|--------|---------|--------------------------------|-------|------|------|----------|------|---------|----------|--------------|
| 比亚迪  | 宋Plus  | 宋Plus EV 2024款 冠军版 605KM | 14.5  | 2024 | 1.2  | SUV      | 上海 | 上海市  | 原版原漆  | 准新车,新能源 |
| 特斯拉  | Model 3 | Model 3 2024款 后轮驱动版     | 22.0  | 2024 | 0.5  | 轿车     | 北京 | 北京市  | 原版原漆  | 新能源,准新车 |
| 大众   | 帕萨特  | 帕萨特 2022款 330TSI 精英版     | 15.8  | 2022 | 3.5  | 轿车     | 广东 | 深圳市  | 轻微剐蹭  | 性价比       |
```

---

## 5. API 接口详解

### 5.1 查询车源

```
GET /api/v1/cars
```

#### 参数

| 参数 | 类型 | 说明 | 示例 |
|------|------|------|------|
| region | string | 省份 | "上海" |
| city | string | 城市 | "上海市" |
| brand | string | 品牌（支持模糊） | "比亚迪" |
| car_type | string | 车型分类 | "SUV" |
| fuel_type | string | 能源类型 | "纯电动" |
| price_min | float | 最低价（万元） | 10 |
| price_max | float | 最高价（万元） | 20 |
| year_min | int | 最低上牌年份 | 2022 |
| status | string | 状态（默认available） | "available" |
| limit | int | 返回数量（默认50，最大100） | 20 |
| offset | int | 偏移量 | 0 |

#### 示例

```bash
# 查询价格在 10-20 万的 SUV
curl -X GET "http://localhost:8000/api/v1/cars?car_type=SUV&price_min=10&price_max=20" \
  -H "X-Api-Key: your_api_key_here"
```

### 5.2 更新车源

```
PUT /api/v1/cars/{car_id}
```

```bash
# 更新价格或状态
curl -X PUT "http://localhost:8000/api/v1/cars/CAR_xxx" \
  -H "X-Api-Key: your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "price": 13.8,
    "status": "reserved"
  }'
```

### 5.3 删除车源

```
DELETE /api/v1/cars/{car_id}
```

```bash
curl -X DELETE "http://localhost:8000/api/v1/cars/CAR_xxx" \
  -H "X-Api-Key: your_api_key_here"
```

### 5.4 获取统计

```
GET /api/v1/stats/my
```

返回当前车商的车源统计，包括：
- 总数量
- 按状态分布
- 按品牌分布（Top 10）
- 按价格区间分布

---

## 6. 错误处理

### 6.1 错误响应格式

```json
{
  "success": false,
  "error": "错误描述",
  "detail": "详细错误信息（可选）"
}
```

### 6.2 HTTP 状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 401 | 认证失败（API Key 无效） |
| 403 | 无权访问 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

### 6.3 常见错误

| 错误信息 | 原因 | 解决方案 |
|----------|------|----------|
| "缺少 API Key" | Header 中未传递 X-Api-Key | 添加 Header |
| "无效的 API Key" | Key 不存在或账户已停用 | 检查 Key 或重新注册 |
| "无权访问此车源" | 试图操作他人的车源 | 仅操作自己上传的车源 |
| "文件解析失败" | Excel 格式错误 | 检查文件格式和列名 |

---

## 7. 示例代码

### 7.1 Python 上传示例

```python
import requests
import openpyxl

# 配置
API_BASE = "http://localhost:8000"
API_KEY = "your_api_key_here"

headers = {"X-Api-Key": API_KEY}

# 上传 Excel
def upload_excel(file_path):
    with open(file_path, "rb") as f:
        files = {"file": (file_path, f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        resp = requests.post(f"{API_BASE}/api/v1/cars/upload", files=files, headers=headers)
    return resp.json()

# 创建单个车源
def create_car(car_data):
    resp = requests.post(f"{API_BASE}/api/v1/cars", json=car_data, headers=headers)
    return resp.json()

# 查询车源
def search_cars(**kwargs):
    resp = requests.get(f"{API_BASE}/api/v1/cars", params=kwargs, headers=headers)
    return resp.json()

# 使用示例
if __name__ == "__main__":
    # 上传 Excel
    result = upload_excel("./cars.xlsx")
    print(f"成功: {result['success_count']}, 失败: {result['error_count']}")
    
    # 查询
    cars = search_cars(brand="比亚迪", price_max=20)
    print(f"找到 {cars['total']} 辆车")
```

### 7.2 JavaScript/Node.js 示例

```javascript
const FormData = require('form-data');
const fs = require('fs');
const axios = require('axios');

const API_BASE = 'http://localhost:8000';
const API_KEY = 'your_api_key_here';

// 上传 Excel
async function uploadExcel(filePath) {
    const form = new FormData();
    form.append('file', fs.createReadStream(filePath));
    
    const response = await axios.post(`${API_BASE}/api/v1/cars/upload`, form, {
        headers: {
            ...form.getHeaders(),
            'X-Api-Key': API_KEY
        }
    });
    return response.data;
}

// 创建车源
async function createCar(carData) {
    const response = await axios.post(`${API_BASE}/api/v1/cars`, carData, {
        headers: { 'X-Api-Key': API_KEY }
    });
    return response.data;
}

// 查询车源
async function searchCars(params) {
    const response = await axios.get(`${API_BASE}/api/v1/cars`, {
        params,
        headers: { 'X-Api-Key': API_KEY }
    });
    return response.data;
}

// 使用
(async () => {
    const result = await uploadExcel('./cars.xlsx');
    console.log(`成功: ${result.success_count}`);
})();
```

---

## 附录：MCP 工具调用

### MCP Server 启动

```bash
# 安装依赖
pip install "mcp[cli]"

# 启动 MCP Server（stdio 模式）
python server.py stdio

# 或使用 mcp dev 进行开发调试
mcp dev server.py
```

### 可用 MCP 工具

| 工具名称 | 功能 |
|---------|------|
| search_cars | 查询车源 |
| get_car_detail | 获取车源详情 |
| match_cars_for_user | 智能匹配推荐 |
| get_car_statistics_summary | 统计概览 |
| get_brands_and_types | 获取可选列表 |
| get_price_range | 价格区间参考 |

详细参数说明请参考 `ARCHITECTURE.md`。
