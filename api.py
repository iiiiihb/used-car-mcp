"""
二手车 MCP 服务器 - REST API 模块

提供 HTTP API 接口供车商上传和管理车源
"""

import json
import hashlib
import hmac
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException, Header, Query, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# 导入数据库模块
from database import (
    verify_api_key, create_dealer, get_dealer, list_dealers,
    create_car, batch_create_cars, get_car, update_car, delete_car,
    list_cars, get_car_statistics
)

# ============ Pydantic 模型 ============

class DealerCreate(BaseModel):
    dealer_name: str
    dealer_type: str = "personal"
    phone: Optional[str] = None
    email: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None


class DealerResponse(BaseModel):
    dealer_id: str
    dealer_name: str
    api_key: str
    api_secret: str  # 仅创建时返回
    region: Optional[str] = None
    status: str


class CarCreate(BaseModel):
    car_id: Optional[str] = None
    brand: str
    series: Optional[str] = None
    model: str
    price: float
    original_price: Optional[float] = None
    year: Optional[int] = None
    month: Optional[int] = None
    mileage: Optional[float] = None
    car_type: Optional[str] = None
    seats: Optional[int] = None
    fuel_type: Optional[str] = None
    transmission: Optional[str] = None
    emission_standard: Optional[str] = None
    color: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    condition: Optional[str] = None
    warranty: Optional[str] = None
    tags: Optional[List[str]] = None
    images: Optional[List[str]] = None


class CarUpdate(BaseModel):
    brand: Optional[str] = None
    series: Optional[str] = None
    model: Optional[str] = None
    price: Optional[float] = None
    original_price: Optional[float] = None
    year: Optional[int] = None
    month: Optional[int] = None
    mileage: Optional[float] = None
    car_type: Optional[str] = None
    seats: Optional[int] = None
    fuel_type: Optional[str] = None
    transmission: Optional[str] = None
    emission_standard: Optional[str] = None
    color: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    condition: Optional[str] = None
    warranty: Optional[str] = None
    tags: Optional[List[str]] = None
    images: Optional[List[str]] = None
    status: Optional[str] = None


class CarQuery(BaseModel):
    region: Optional[str] = None
    city: Optional[str] = None
    brand: Optional[str] = None
    car_type: Optional[str] = None
    fuel_type: Optional[str] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    year_min: Optional[int] = None
    limit: int = Field(default=50, le=100)
    offset: int = 0


# ============ FastAPI 应用 ============

app = FastAPI(
    title="二手车 MCP 服务器 API",
    description="车商车源管理接口",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ 辅助函数 ============

async def get_current_dealer(x_api_key: str = Header(None)) -> Dict[str, Any]:
    """验证 API Key 并返回车商信息"""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="缺少 API Key")
    
    dealer = verify_api_key(x_api_key)
    if not dealer:
        raise HTTPException(status_code=401, detail="无效的 API Key 或账户已停用")
    
    return dealer


def parse_excel_to_cars(file_content: bytes, dealer_id: str) -> List[Dict[str, Any]]:
    """解析 Excel 文件为车源数据列表"""
    import io
    import openpyxl
    
    wb = openpyxl.load_workbook(io.BytesIO(file_content))
    sheet = wb.active
    
    # 读取表头（第一行）
    headers = []
    for cell in sheet[1]:
        headers.append(cell.value)
    
    # 中文到英文字段映射
    field_mapping = {
        "品牌": "brand",
        "车系": "series",
        "车型": "model",
        "价格": "price",
        "价格(万)": "price",
        "新车价": "original_price",
        "新车价(万)": "original_price",
        "年份": "year",
        "月份": "month",
        "里程": "mileage",
        "里程(万)": "mileage",
        "车型分类": "car_type",
        "座位数": "seats",
        "能源类型": "fuel_type",
        "变速箱": "transmission",
        "排放标准": "emission_standard",
        "颜色": "color",
        "省份": "region",
        "城市": "city",
        "地址": "address",
        "车况": "condition",
        "质保": "warranty",
        "标签": "tags",
    }
    
    cars = []
    for row in sheet.iter_rows(min_row=2, values_only=True):
        if not row[0]:  # 跳过空行
            continue
        
        car_data = {"dealer_id": dealer_id}
        
        for i, header in enumerate(headers):
            if header and i < len(row):
                mapped_key = field_mapping.get(str(header), str(header))
                value = row[i]
                
                # 类型转换
                if mapped_key == "price" and value:
                    car_data[mapped_key] = float(value)
                elif mapped_key in ["original_price", "mileage"] and value:
                    car_data[mapped_key] = float(value)
                elif mapped_key in ["year", "month", "seats"] and value:
                    car_data[mapped_key] = int(value)
                elif mapped_key == "tags" and value:
                    # 逗号分隔的标签
                    car_data[mapped_key] = [t.strip() for t in str(value).split(",") if t.strip()]
                else:
                    car_data[mapped_key] = value
        
        if "brand" in car_data and "model" in car_data and "price" in car_data:
            cars.append(car_data)
    
    return cars


# ============ 车商注册接口 ============

@app.post("/api/v1/dealers/register", response_model=DealerResponse)
async def register_dealer(dealer: DealerCreate):
    """注册新车商（获取 API Key）"""
    
    # 创建车商
    dealer_data = dealer.model_dump()
    dealer_id = create_dealer(dealer_data)
    
    # 获取完整信息（包含 API Key）
    full_dealer = get_dealer(dealer_id)
    
    return DealerResponse(
        dealer_id=full_dealer["dealer_id"],
        dealer_name=full_dealer["dealer_name"],
        api_key=full_dealer["api_key"],
        api_secret=full_dealer["api_secret"],
        region=full_dealer.get("region"),
        status=full_dealer["status"]
    )


@app.get("/api/v1/dealers/me")
async def get_my_info(x_api_key: str = Header(None)):
    """获取当前车商信息"""
    dealer = await get_current_dealer(x_api_key)
    
    # 不返回敏感信息
    return {
        "dealer_id": dealer["dealer_id"],
        "dealer_name": dealer["dealer_name"],
        "dealer_type": dealer["dealer_type"],
        "region": dealer.get("region"),
        "city": dealer.get("city"),
        "status": dealer["status"],
        "created_at": dealer["created_at"]
    }


# ============ 车源上传接口 ============

@app.post("/api/v1/cars/upload")
async def upload_cars(
    x_api_key: str = Header(None),
    file: UploadFile = File(...)
):
    """
    上传 Excel 文件批量导入车源
    
    支持格式: .xlsx, .xls, .csv
    
    Excel 表头要求（支持中文列名）:
    - 品牌*、车系、车型*、价格*、新车价、年份、月份、里程
    - 车型分类、座位数、能源类型、变速箱、排放标准
    - 颜色、省份、城市、地址、车况、质保、标签
    
    * 为必填字段
    """
    dealer = await get_current_dealer(x_api_key)
    
    # 读取文件
    content = await file.read()
    
    # 检查文件类型
    filename = file.filename.lower()
    if not filename.endswith(('.xlsx', '.xls', '.csv')):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx, .xls, .csv 格式")
    
    # 解析文件
    try:
        cars_data = parse_excel_to_cars(content, dealer["dealer_id"])
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文件解析失败: {str(e)}")
    
    if not cars_data:
        raise HTTPException(status_code=400, detail="文件中未找到有效车源数据")
    
    # 批量导入
    result = batch_create_cars(cars_data)
    
    return {
        "message": "导入完成",
        "total": len(cars_data),
        "success_count": result["success_count"],
        "error_count": result["error_count"],
        "errors": result["errors"] if result["errors"] else None
    }


@app.post("/api/v1/cars")
async def create_single_car(
    car: CarCreate,
    x_api_key: str = Header(None)
):
    """创建单个车源"""
    dealer = await get_current_dealer(x_api_key)
    
    car_data = car.model_dump()
    car_data["dealer_id"] = dealer["dealer_id"]
    car_data["source"] = "api"
    
    car_id = create_car(car_data)
    
    return {"car_id": car_id, "message": "创建成功"}


@app.get("/api/v1/cars")
async def query_cars(
    x_api_key: str = Header(None),
    region: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    brand: Optional[str] = Query(None),
    car_type: Optional[str] = Query(None),
    fuel_type: Optional[str] = Query(None),
    price_min: Optional[float] = Query(None),
    price_max: Optional[float] = Query(None),
    year_min: Optional[int] = Query(None),
    status: str = Query("available"),
    limit: int = Query(50, le=100),
    offset: int = Query(0)
):
    """查询车源列表"""
    dealer = await get_current_dealer(x_api_key)
    
    result = list_cars(
        dealer_id=dealer["dealer_id"],
        region=region,
        city=city,
        brand=brand,
        car_type=car_type,
        fuel_type=fuel_type,
        price_min=price_min,
        price_max=price_max,
        year_min=year_min,
        status=status,
        limit=limit,
        offset=offset
    )
    
    return result


@app.get("/api/v1/cars/{car_id}")
async def get_single_car(
    car_id: str,
    x_api_key: str = Header(None)
):
    """获取单个车源详情"""
    dealer = await get_current_dealer(x_api_key)
    
    car = get_car(car_id)
    
    if not car:
        raise HTTPException(status_code=404, detail="车源不存在")
    
    # 检查权限（只能查看自己的车源）
    if car["dealer_id"] != dealer["dealer_id"]:
        raise HTTPException(status_code=403, detail="无权访问此车源")
    
    return car


@app.put("/api/v1/cars/{car_id}")
async def update_single_car(
    car_id: str,
    car: CarUpdate,
    x_api_key: str = Header(None)
):
    """更新车源"""
    dealer = await get_current_dealer(x_api_key)
    
    existing_car = get_car(car_id)
    if not existing_car:
        raise HTTPException(status_code=404, detail="车源不存在")
    
    if existing_car["dealer_id"] != dealer["dealer_id"]:
        raise HTTPException(status_code=403, detail="无权修改此车源")
    
    car_data = car.model_dump(exclude_unset=True)
    success = update_car(car_id, car_data)
    
    if not success:
        raise HTTPException(status_code=500, detail="更新失败")
    
    return {"message": "更新成功"}


@app.delete("/api/v1/cars/{car_id}")
async def delete_single_car(
    car_id: str,
    x_api_key: str = Header(None)
):
    """删除车源（软删除）"""
    dealer = await get_current_dealer(x_api_key)
    
    existing_car = get_car(car_id)
    if not existing_car:
        raise HTTPException(status_code=404, detail="车源不存在")
    
    if existing_car["dealer_id"] != dealer["dealer_id"]:
        raise HTTPException(status_code=403, detail="无权删除此车源")
    
    success = delete_car(car_id)
    
    if not success:
        raise HTTPException(status_code=500, detail="删除失败")
    
    return {"message": "删除成功"}


# ============ 统计接口 ============

@app.get("/api/v1/stats/my")
async def get_my_statistics(x_api_key: str = Header(None)):
    """获取我的车源统计"""
    dealer = await get_current_dealer(x_api_key)
    return get_car_statistics(dealer["dealer_id"])


# ============ 健康检查 ============

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


# ============ 导出 FastAPI 应用 ============

def create_api_app():
    """创建 API 应用（供 MCP Server 内部使用）"""
    return app


if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
