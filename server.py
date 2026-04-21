#!/usr/bin/env python3
"""
二手车 MCP 服务器 - 主入口

使用 FastMCP 框架实现 Model Context Protocol 服务端
提供车源查询、筛选、统计等工具给 AI 应用使用
"""

import json
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime

# MCP 相关导入
from mcp.server.fastmcp import FastMCP
from mcp.types import Resource, Tool

# 导入数据库模块
from database import (
    get_car, list_cars, get_car_statistics,
    verify_api_key, get_dealer
)

# 导入 API 模块（用于 Excel 解析）
from api import parse_excel_to_cars

# ============ 创建 MCP Server ============

mcp = FastMCP(
    name="used-car-mcp",
    version="1.0.0",
    description="二手车车源查询与管理服务"
)


# ============ MCP 工具定义 ============

@mcp.tool()
async def search_cars(
    region: Optional[str] = None,
    city: Optional[str] = None,
    brand: Optional[str] = None,
    car_type: Optional[str] = None,
    fuel_type: Optional[str] = None,
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    year_min: Optional[int] = None,
    limit: int = 20
) -> str:
    """
    查询二手车源
    
    参数:
        region: 省份/地区（如"上海"、"广东"）
        city: 城市（如"上海市"、"深圳市"）
        brand: 品牌（如"比亚迪"、"特斯拉"）
        car_type: 车型分类（轿车/SUV/MPV/跑车）
        fuel_type: 能源类型（汽油/纯电动/插电混动/油电混动）
        price_min: 最低价格（万元）
        price_max: 最高价格（万元）
        year_min: 最低上牌年份
        limit: 返回数量（默认20，最大50）
    
    返回:
        JSON 格式的车源列表
    """
    if limit > 50:
        limit = 50
    
    result = list_cars(
        region=region,
        city=city,
        brand=brand,
        car_type=car_type,
        fuel_type=fuel_type,
        price_min=price_min,
        price_max=price_max,
        year_min=year_min,
        limit=limit
    )
    
    if not result["cars"]:
        return json.dumps({
            "success": True,
            "message": "未找到符合条件的车辆",
            "total": 0,
            "cars": []
        }, ensure_ascii=False, indent=2)
    
    return json.dumps({
        "success": True,
        "message": f"找到 {result['total']} 辆符合条件的车辆",
        "total": result["total"],
        "returned": len(result["cars"]),
        "cars": result["cars"]
    }, ensure_ascii=False, indent=2)


@mcp.tool()
async def get_car_detail(car_id: str) -> str:
    """
    获取车源详情
    
    参数:
        car_id: 车源ID
    
    返回:
        JSON 格式的车源详细信息
    """
    car = get_car(car_id)
    
    if not car:
        return json.dumps({
            "success": False,
            "error": f"未找到车源: {car_id}"
        }, ensure_ascii=False, indent=2)
    
    return json.dumps({
        "success": True,
        "car": car
    }, ensure_ascii=False, indent=2)


@mcp.tool()
async def match_cars_for_user(
    budget_min: float = 5,
    budget_max: float = 15,
    preferred_brands: Optional[str] = None,
    preferred_types: Optional[str] = None,
    region: Optional[str] = None,
    city: Optional[str] = None,
    need_loan: bool = False,
    limit: int = 10
) -> str:
    """
    根据用户偏好智能匹配车源（核心功能）
    
    这是二手车推荐的核心算法，综合考虑用户预算、品牌偏好、
    车型偏好、地区等因素进行智能匹配和排序。
    
    参数:
        budget_min: 最低预算（万元）
        budget_max: 最高预算（万元）
        preferred_brands: 偏好的品牌列表，逗号分隔（如"比亚迪,特斯拉"）
        preferred_types: 偏好的车型列表，逗号分隔（如"SUV,轿车"）
        region: 所在省份
        city: 所在城市
        need_loan: 是否需要贷款
        limit: 返回数量（默认10）
    
    返回:
        JSON 格式的推荐车源列表，包含匹配度评分
    """
    # 解析偏好列表
    brands = [b.strip() for b in preferred_brands.split(",")] if preferred_brands else []
    types = [t.strip() for t in preferred_types.split(",")] if preferred_types else []
    
    # 查询候选车源（在更大范围内查询以便评分）
    candidate_limit = limit * 3  # 多查询一些以便筛选
    result = list_cars(
        region=region,
        city=city,
        brand=preferred_brands,  # 优先品牌的
        car_type=preferred_types,
        price_min=budget_min * 0.7,  # 扩大范围以便推荐
        price_max=budget_max * 1.2,
        limit=candidate_limit
    )
    
    if not result["cars"]:
        # 扩大范围重试
        result = list_cars(
            price_min=budget_min * 0.5,
            price_max=budget_max * 1.5,
            limit=candidate_limit
        )
    
    cars = result["cars"]
    
    # 计算匹配度评分
    scored_cars = []
    for car in cars:
        score = calc_match_score(
            car=car,
            budget_min=budget_min,
            budget_max=budget_max,
            preferred_brands=brands,
            preferred_types=types,
            user_city=city or region
        )
        scored_cars.append({
            **car,
            "match_score": score
        })
    
    # 按匹配度排序
    scored_cars.sort(key=lambda x: x["match_score"], reverse=True)
    
    # 取 Top N
    top_cars = scored_cars[:limit]
    
    # 添加贷款信息（如果需要）
    if need_loan:
        for car in top_cars:
            car["loan_estimate"] = estimate_loan(car["price"])
    
    return json.dumps({
        "success": True,
        "user_preferences": {
            "budget": f"{budget_min}-{budget_max}万",
            "brands": brands or "不限",
            "types": types or "不限",
            "region": region or city or "不限",
            "need_loan": need_loan
        },
        "total_candidates": len(cars),
        "returned": len(top_cars),
        "recommendations": top_cars
    }, ensure_ascii=False, indent=2)


def calc_match_score(
    car: Dict[str, Any],
    budget_min: float,
    budget_max: float,
    preferred_brands: List[str],
    preferred_types: List[str],
    user_city: Optional[str]
) -> int:
    """
    计算车源匹配度评分 (0-100)
    
    评分规则:
    - 预算匹配: 0-40分
    - 品牌匹配: 0-20分
    - 车型匹配: 0-15分
    - 地区匹配: 0-15分
    - 车况/性价比: 0-10分
    """
    score = 0
    
    price = car.get("price", 0)
    
    # 1. 预算匹配 (0-40分)
    if budget_min <= price <= budget_max:
        # 在预算内，得满分
        if price >= budget_min * 0.9 and price <= budget_max * 0.95:
            score += 40  # 最佳区间
        else:
            score += 35
    elif price < budget_min:
        # 低于预算太多，性价比高但可能超出预期
        diff_ratio = (budget_min - price) / budget_min
        if diff_ratio <= 0.2:
            score += 30
        else:
            score += 20
    else:
        # 超出预算
        diff_ratio = (price - budget_max) / budget_max
        if diff_ratio <= 0.1:
            score += 25
        elif diff_ratio <= 0.2:
            score += 15
        elif diff_ratio <= 0.3:
            score += 5
        # 超出 >30% 得 0 分
    
    # 2. 品牌匹配 (0-20分)
    car_brand = car.get("brand", "")
    if preferred_brands:
        if car_brand in preferred_brands:
            score += 20
        elif any(pb in car_brand for pb in preferred_brands):
            score += 15
        else:
            score += 5  # 无偏好品牌给基础分
    else:
        score += 10  # 无品牌偏好
    
    # 3. 车型匹配 (0-15分)
    car_type = car.get("car_type", "")
    if preferred_types:
        if car_type in preferred_types:
            score += 15
        else:
            score += 5
    else:
        score += 10
    
    # 4. 地区匹配 (0-15分)
    car_city = car.get("city", "")
    if user_city:
        if car_city == user_city:
            score += 15
        elif car_city and user_city and (car_city[:2] == user_city[:2] or car_city in user_city or user_city in car_city):
            score += 10
        else:
            score += 5
    else:
        score += 10
    
    # 5. 车况/性价比 (0-10分)
    condition = car.get("condition", "")
    if condition == "原版原漆":
        score += 10
    elif condition == "轻微剐蹭":
        score += 7
    elif condition == "有过维修":
        score += 4
    else:
        score += 2
    
    # 折扣率加分
    discount_rate = car.get("discount_rate")
    if discount_rate and discount_rate < 0.8:
        score += 3  # 高折扣
    
    return min(score, 100)


def estimate_loan(price: float, down_payment_ratio: float = 0.3, years: int = 3) -> Dict[str, Any]:
    """
    估算贷款方案
    
    参数:
        price: 车辆总价（万元）
        down_payment_ratio: 首付比例
        years: 贷款年限
    
    返回:
        贷款估算信息
    """
    down_payment = round(price * down_payment_ratio, 2)
    loan_amount = round(price - down_payment, 2)
    
    # 假设年利率 4.75%（银行基准）
    annual_rate = 0.0475
    months = years * 12
    
    # 等额本息月供计算
    monthly_rate = annual_rate / 12
    if monthly_rate > 0:
        monthly_payment = loan_amount * monthly_rate * ((1 + monthly_rate) ** months) / ((1 + monthly_rate) ** months - 1)
    else:
        monthly_payment = loan_amount / months
    
    total_interest = monthly_payment * months - loan_amount
    total_payment = monthly_payment * months
    
    return {
        "vehicle_price": price,
        "down_payment": down_payment,
        "down_payment_ratio": down_payment_ratio,
        "loan_amount": loan_amount,
        "annual_rate": annual_rate,
        "loan_term_years": years,
        "monthly_payment": round(monthly_payment, 2),
        "total_interest": round(total_interest, 2),
        "total_payment": round(total_payment, 2)
    }


@mcp.tool()
async def get_car_statistics_summary() -> str:
    """
    获取车源统计概览
    
    返回平台整体的车源统计数据，包括：
    - 总车源数量
    - 按状态分布
    - 按品牌分布（Top 10）
    - 按价格区间分布
    """
    stats = get_car_statistics()
    
    return json.dumps({
        "success": True,
        "statistics": stats,
        "generated_at": datetime.now().isoformat()
    }, ensure_ascii=False, indent=2)


@mcp.tool()
async def get_brands_and_types() -> str:
    """
    获取可选的品牌和车型列表
    
    返回系统中所有可用的品牌和车型分类选项，
    用于构建查询条件或用户界面。
    """
    # 查询所有不同的品牌
    result = list_cars(limit=500)
    
    brands = set()
    car_types = set()
    fuel_types = set()
    
    for car in result["cars"]:
        if car.get("brand"):
            brands.add(car["brand"])
        if car.get("car_type"):
            car_types.add(car["car_type"])
        if car.get("fuel_type"):
            fuel_types.add(car["fuel_type"])
    
    return json.dumps({
        "success": True,
        "brands": sorted(list(brands)),
        "car_types": sorted(list(car_types)),
        "fuel_types": sorted(list(fuel_types))
    }, ensure_ascii=False, indent=2)


@mcp.tool()
async def get_price_range(brand: Optional[str] = None) -> str:
    """
    获取价格区间参考
    
    参数:
        brand: 可选的品牌筛选
    
    返回指定品牌或全部车辆的价格区间统计，
    帮助用户了解市场行情。
    """
    result = list_cars(brand=brand, limit=500)
    
    if not result["cars"]:
        return json.dumps({
            "success": True,
            "message": "暂无数据",
            "price_range": None
        }, ensure_ascii=False)
    
    prices = [car["price"] for car in result["cars"] if car.get("price")]
    
    if not prices:
        return json.dumps({
            "success": True,
            "message": "价格数据不完整",
            "price_range": None
        }, ensure_ascii=False)
    
    return json.dumps({
        "success": True,
        "filter": {"brand": brand} if brand else "all",
        "price_range": {
            "min": min(prices),
            "max": max(prices),
            "avg": round(sum(prices) / len(prices), 2),
            "median": round(sorted(prices)[len(prices) // 2], 2)
        },
        "total_cars": len(prices)
    }, ensure_ascii=False, indent=2)


@mcp.tool()
async def batch_import_cars_from_json(cars_json: str) -> str:
    """
    批量导入车源（JSON格式）
    
    参数:
        cars_json: 车源数据的 JSON 数组字符串
    
    此工具用于从其他数据源批量导入车源数据。
    每个车源应包含必要字段：brand, model, price
    """
    try:
        cars_data = json.loads(cars_json)
    except json.JSONDecodeError as e:
        return json.dumps({
            "success": False,
            "error": f"JSON 解析失败: {str(e)}"
        }, ensure_ascii=False)
    
    if not isinstance(cars_data, list):
        return json.dumps({
            "success": False,
            "error": "数据格式错误，需要 JSON 数组"
        }, ensure_ascii=False)
    
    # 验证必要字段
    required_fields = ["brand", "model", "price"]
    valid_cars = []
    errors = []
    
    for i, car in enumerate(cars_data):
        missing = [f for f in required_fields if f not in car or not car[f]]
        if missing:
            errors.append(f"第 {i+1} 条数据缺少字段: {', '.join(missing)}")
        else:
            valid_cars.append(car)
    
    if not valid_cars:
        return json.dumps({
            "success": False,
            "error": "没有有效的数据",
            "errors": errors
        }, ensure_ascii=False, indent=2)
    
    # 这里简化处理，实际应该导入到数据库
    return json.dumps({
        "success": True,
        "message": f"接收到 {len(valid_cars)} 条有效数据",
        "total_received": len(cars_data),
        "valid_count": len(valid_cars),
        "errors": errors if errors else None
    }, ensure_ascii=False, indent=2)


# ============ 需求库工具 ============

@mcp.tool()
async def submit_demand(
    user_id: str,
    budget_min: float,
    budget_max: float,
    user_nickname: Optional[str] = None,
    preferred_brands: Optional[str] = None,
    preferred_types: Optional[str] = None,
    region: Optional[str] = None,
    city: Optional[str] = None,
    notes: Optional[str] = None
) -> str:
    """
    提交用户购车需求
    
    参数:
        user_id: 用户唯一标识
        budget_min: 最低预算（万元）
        budget_max: 最高预算（万元）
        user_nickname: 用户昵称
        preferred_brands: 偏好品牌（逗号分隔，如"丰田,本田"）
        preferred_types: 偏好车型（逗号分隔，如"SUV,轿车"）
        region: 所在省份
        city: 所在城市
        notes: 备注信息
    
    返回:
        提交结果，包含需求ID和阈值检测结果
    """
    from database import create_demand, get_budget_segment
    import json
    from datetime import datetime, timedelta
    
    # 解析偏好
    brands = [b.strip() for b in preferred_brands.split(",")] if preferred_brands else []
    car_types = [t.strip() for t in preferred_types.split(",")] if preferred_types else []
    
    # 计算价位段
    budget_segment = get_budget_segment(budget_min, budget_max)
    
    # 计算过期时间
    expires_at = (datetime.now() + timedelta(days=7)).isoformat()
    
    # 构建偏好配置
    preferences = {
        "budget_min": budget_min,
        "budget_max": budget_max,
        "budget_segment": budget_segment,
        "brands": brands,
        "car_types": car_types,
        "fuel_types": [],
        "region": region,
        "city": city
    }
    
    # 生成需求ID
    from database import generate_demand_id
    demand_id = generate_demand_id()
    
    # 构建需求数据
    demand_data = {
        "demand_id": demand_id,
        "user_id": user_id,
        "user_nickname": user_nickname or user_id,
        "preferences": preferences,
        "budget_segment": budget_segment,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "expires_at": expires_at,
        "matched_count": 0,
        "notes": notes or ""
    }
    
    # 创建需求
    create_demand(demand_data)
    
    # 检查阈值
    from database import check_threshold_demands
    threshold_result = check_threshold_demands(
        region=region,
        budget_segment=budget_segment,
        threshold=8
    )
    
    # 检查是否触发
    triggered = False
    triggered_segments = []
    for seg in threshold_result.get("triggered_segments", []):
        if seg["region"] == (region or "未知"):
            triggered = True
            triggered_segments.append(seg)
            break
    
    return json.dumps({
        "success": True,
        "demand_id": demand_id,
        "budget_segment": budget_segment,
        "expires_at": expires_at,
        "threshold_triggered": triggered,
        "triggered_segments": triggered_segments,
        "threshold_result": {
            "threshold": threshold_result.get("threshold"),
            "total_pending": threshold_result.get("total_pending"),
            "segments_count": len(threshold_result.get("segments", []))
        }
    }, ensure_ascii=False, indent=2)


@mcp.tool()
async def check_threshold(
    region: Optional[str] = None,
    budget_segment: Optional[str] = None
) -> str:
    """
    检查团购阈值状态（加权计算版本）
    
    参数:
        region: 省份/地区（可选）
        budget_segment: 价位段（可选，如"10-15万"）
    
    返回:
        各地区+价位段组合的阈值检测结果，包含加权分数和分层详情
    """
    from database import check_threshold_demands
    import json
    
    result = check_threshold_demands(
        region=region,
        budget_segment=budget_segment,
        threshold=8
    )
    
    # 格式化返回结果
    segments_info = []
    for seg in result.get("segments", []):
        tier_stats = seg.get("tier_stats", {})
        
        # 计算加权总分
        weighted_score = sum(t.get("total", 0) for t in tier_stats.values())
        
        # 格式化分层统计
        formatted_tiers = []
        for tier in ["active", "stale", "old", "aging", "archived"]:
            if tier in tier_stats and tier_stats[tier]["count"] > 0:
                formatted_tiers.append({
                    "tier": tier,
                    "count": tier_stats[tier]["count"],
                    "weight": tier_stats[tier]["weight"],
                    "total": tier_stats[tier]["total"]
                })
        
        segments_info.append({
            "region": seg["region"],
            "budget_segment": seg["budget_segment"],
            "total_demands": seg["count"],
            "weighted_score": round(weighted_score, 2),
            "threshold": seg["threshold"],
            "triggered": weighted_score >= seg["threshold"],
            "tier_stats": formatted_tiers,
            "brand_preferences": seg.get("brand_stats", {}),
            "type_preferences": seg.get("type_stats", {})
        })
    
    return json.dumps({
        "success": True,
        "threshold": result.get("threshold"),
        "total_pending": result.get("total_pending"),
        "segments": segments_info,
        "triggered_segments": [s for s in segments_info if s["triggered"]]
    }, ensure_ascii=False, indent=2)


@mcp.tool()
async def get_demands(
    region: Optional[str] = None,
    budget_segment: Optional[str] = None,
    status: Optional[str] = None,
    time_status: Optional[str] = None,
    limit: int = 50
) -> str:
    """
    获取需求列表（支持按时间状态筛选）
    
    参数:
        region: 省份/地区筛选
        budget_segment: 价位段筛选
        status: 业务状态筛选（pending/matched/group_buy_triggered/expired/cancelled）
        time_status: 时间分层状态筛选（active/stale/old/aging/archived）
        limit: 返回数量（默认50）
    
    返回:
        需求列表
    """
    from database import list_demands
    import json
    from datetime import datetime, timedelta
    
    # 解析状态
    if time_status:
        # 时间分层状态需要特殊处理
        # 根据时间状态计算时间范围
        now = datetime.now()
        if time_status == "active":
            date_min = (now - timedelta(days=14)).isoformat()
            date_max = now.isoformat()
        elif time_status == "stale":
            date_min = (now - timedelta(days=90)).isoformat()
            date_max = (now - timedelta(days=14)).isoformat()
        elif time_status == "old":
            date_min = (now - timedelta(days=180)).isoformat()
            date_max = (now - timedelta(days=90)).isoformat()
        elif time_status == "aging":
            date_min = (now - timedelta(days=365)).isoformat()
            date_max = (now - timedelta(days=180)).isoformat()
        elif time_status == "archived":
            date_min = "2000-01-01T00:00:00"
            date_max = (now - timedelta(days=365)).isoformat()
        else:
            date_min = None
            date_max = None
        
        # 查询所有 pending 状态的需求，然后按时间筛选
        result = list_demands(status=status or "pending", limit=500)
        
        demands = []
        for d in result.get("demands", []):
            created_at = d.get("created_at", "")
            if date_min and date_max:
                if date_min <= created_at <= date_max:
                    demands.append(d)
            if len(demands) >= limit:
                break
    else:
        result = list_demands(
            user_id=None,
            status=status,
            region=region,
            limit=limit
        )
        demands = result.get("demands", [])
    
    # 为每个需求添加时间状态信息
    for demand in demands:
        from database import _get_demand_time_status
        time_status_result, weight = _get_demand_time_status(demand.get("created_at"))
        demand["time_status"] = time_status_result
        demand["weight"] = weight
    
    # 按 region 和 budget_segment 过滤
    if region or budget_segment:
        filtered = []
        for d in demands:
            pref = d.get("preferences", {})
            if region and pref.get("region") != region:
                continue
            if budget_segment and pref.get("budget_segment") != budget_segment:
                continue
            filtered.append(d)
        demands = filtered
    
    return json.dumps({
        "success": True,
        "total": len(demands),
        "returned": len(demands),
        "demands": demands
    }, ensure_ascii=False, indent=2)


@mcp.tool()
async def get_demand_statistics_summary() -> str:
    """
    获取需求统计概览
    
    返回各时间分层的需求统计信息，包括：
    - 总需求数
    - 各时间分层的需求数和加权分数
    - 各价位段的需求分布
    - 达到阈值的组合
    """
    from database import get_demand_statistics, check_threshold_demands
    import json
    from datetime import datetime, timedelta
    
    # 获取基础统计
    base_stats = get_demand_statistics()
    
    # 获取阈值检测结果
    threshold_result = check_threshold_demands(threshold=8)
    
    # 计算各时间分层的统计
    tier_summary = {
        "active": {"count": 0, "weighted": 0.0},
        "stale": {"count": 0, "weighted": 0.0},
        "old": {"count": 0, "weighted": 0.0},
        "aging": {"count": 0, "weighted": 0.0},
        "archived": {"count": 0, "weighted": 0.0}
    }
    
    tier_labels = {
        "active": "活跃（14天内）",
        "stale": "陈旧（14天-3月）",
        "old": "较旧（3月-半年）",
        "aging": "老化（半年-1年）",
        "archived": "归档（超过1年）"
    }
    
    for seg in threshold_result.get("segments", []):
        tier_stats = seg.get("tier_stats", {})
        for tier, stats in tier_stats.items():
            if tier in tier_summary:
                tier_summary[tier]["count"] += stats["count"]
                tier_summary[tier]["weighted"] += stats["total"]
    
    # 格式化分层统计
    tier_display = []
    for tier, stats in tier_summary.items():
        if stats["count"] > 0:
            tier_display.append({
                "tier": tier,
                "label": tier_labels.get(tier, tier),
                "count": stats["count"],
                "weighted_score": round(stats["weighted"], 2),
                "percentage": round(stats["count"] / base_stats["total"] * 100, 1) if base_stats["total"] > 0 else 0
            })
    
    return json.dumps({
        "success": True,
        "total_demands": base_stats["total"],
        "pending_demands": base_stats["by_status"].get("pending", 0),
        "tier_summary": tier_display,
        "triggered_count": len(threshold_result.get("triggered_segments", [])),
        "triggered_segments": threshold_result.get("triggered_segments", []),
        "threshold": 8,
        "generated_at": datetime.now().isoformat()
    }, ensure_ascii=False, indent=2)


# ============ MCP 资源定义 ============

@mcp.resource("config://app_info")
async def get_app_config() -> str:
    """获取应用配置信息"""
    return json.dumps({
        "name": "二手车 MCP 服务器",
        "version": "1.0.0",
        "description": "提供二手车源查询、匹配、管理等功能"
    }, ensure_ascii=False)


@mcp.resource("schema://car")
async def get_car_schema() -> str:
    """获取车源数据结构定义"""
    return json.dumps({
        "required_fields": ["brand", "model", "price"],
        "optional_fields": [
            "series", "year", "month", "mileage", "car_type",
            "seats", "fuel_type", "transmission", "emission_standard",
            "color", "region", "city", "condition", "warranty", "tags"
        ],
        "enum_values": {
            "car_type": ["轿车", "SUV", "MPV", "跑车", "皮卡", "面包车", "其他"],
            "fuel_type": ["汽油", "柴油", "纯电动", "插电混动", "油电混动", "增程式"],
            "transmission": ["手动", "自动", "无级变速"],
            "emission_standard": ["国五", "国六", "国六B", "新能源"],
            "condition": ["原版原漆", "轻微剐蹭", "有过维修", "事故车"]
        }
    }, ensure_ascii=False, indent=2)


# ============ MCP 提示模板 ============

@mcp.prompt()
async def car_search_prompt(query: str) -> str:
    """二手车搜索提示模板"""
    return f"""用户想要搜索二手车，请根据以下需求调用适当的工具：

用户需求: {query}

建议的搜索流程：
1. 首先理解用户的预算、偏好
2. 调用 search_cars 或 match_cars_for_user 进行查询
3. 根据返回结果向用户推荐匹配的车源
4. 如需贷款，可调用 match_cars_for_user 并设置 need_loan=true
"""


@mcp.prompt()
async def car_comparison_prompt(car_ids: str) -> str:
    """车辆对比提示模板"""
    return f"""用户想要对比以下车辆，请获取详细信息并进行比较：

车源ID列表: {car_ids}

对比维度建议：
1. 价格对比
2. 车龄/里程对比
3. 配置差异
4. 性价比分析
5. 建议购买选项
"""


# 导入数据库模块 - 需求库
from database import (
    create_demand, get_demand, update_demand, delete_demand, list_demands,
    check_threshold_demands, mark_demand_as_matched, mark_demand_as_group_buy_triggered,
    cleanup_expired_demands, get_demand_statistics
)


# ============ 需求库 MCP 工具 ============

@mcp.tool()
async def submit_demand(
    user_id: str,
    budget_min: float,
    budget_max: float,
    user_nickname: Optional[str] = None,
    preferred_brands: Optional[str] = None,
    preferred_types: Optional[str] = None,
    region: Optional[str] = None,
    city: Optional[str] = None,
    notes: Optional[str] = None
) -> str:
    """
    提交用户购车需求到需求库
    
    当没有匹配到合适车源时，将用户需求存储到需求库，
    达到阈值后自动触发团购通知。
    
    参数:
        user_id: 用户唯一标识（必填）
        budget_min: 最低预算（万元）（必填）
        budget_max: 最高预算（万元）（必填）
        user_nickname: 用户昵称（可选）
        preferred_brands: 偏好品牌，逗号分隔（如"丰田,本田"）
        preferred_types: 偏好车型，逗号分隔（如"SUV,轿车"）
        region: 所在省份/地区
        city: 所在城市
        notes: 备注信息
    
    返回:
        JSON 格式的提交结果，包含需求ID和阈值检测结果
    """
    # 构建偏好配置
    preferences = {
        "budget_min": budget_min,
        "budget_max": budget_max,
        "brands": [b.strip() for b in preferred_brands.split(",")] if preferred_brands else [],
        "car_types": [t.strip() for t in preferred_types.split(",")] if preferred_types else [],
        "region": region,
        "city": city
    }
    
    # 创建需求
    demand_data = {
        "user_id": user_id,
        "user_nickname": user_nickname or user_id,
        "preferences": preferences,
        "notes": notes or ""
    }
    
    try:
        demand_id = create_demand(demand_data)
        
        # 检查阈值
        threshold_result = check_threshold_demands(
            region=region,
            threshold=8
        )
        
        return json.dumps({
            "success": True,
            "message": "需求已提交到需求库",
            "demand_id": demand_id,
            "expires_in_days": 7,
            "threshold_check": {
                "threshold": threshold_result["threshold"],
                "triggered": len(threshold_result["triggered_segments"]) > 0,
                "message": "已触发团购！" if threshold_result["triggered_segments"] else f"还需{8 - sum(s['count'] for s in threshold_result['segments'] if s['region'] == (region or '未知'))}条需求即可触发团购"
            }
        }, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"提交需求失败: {str(e)}"
        }, ensure_ascii=False, indent=2)


@mcp.tool()
async def check_threshold(
    region: Optional[str] = None,
    budget_segment: Optional[str] = None
) -> str:
    """
    检查需求库阈值状态
    
    查看指定地区和价位段的需求积累情况，
    判断是否达到团购触发阈值。
    
    参数:
        region: 省份/地区（可选）
        budget_segment: 价位段（可选，如"10-15万"）
    
    返回:
        JSON 格式的阈值检测结果
    """
    try:
        result = check_threshold_demands(
            region=region,
            budget_segment=budget_segment,
            threshold=8
        )
        
        return json.dumps({
            "success": True,
            "threshold": result["threshold"],
            "total_pending": result["total_pending"],
            "segments": result["segments"],
            "triggered_segments": result["triggered_segments"],
            "triggered": len(result["triggered_segments"]) > 0
        }, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"检查阈值失败: {str(e)}"
        }, ensure_ascii=False, indent=2)


@mcp.tool()
async def get_demands_list(
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 20
) -> str:
    """
    查询需求列表（运营方使用）
    
    获取需求库中的需求记录，支持按用户和状态筛选。
    
    参数:
        user_id: 用户ID（可选，筛选指定用户的需求）
        status: 需求状态（可选：pending, matched, group_buy_triggered, expired）
        limit: 返回数量（默认20）
    
    返回:
        JSON 格式的需求列表
    """
    try:
        result = list_demands(
            user_id=user_id,
            status=status,
            limit=limit
        )
        
        return json.dumps({
            "success": True,
            "total": result["total"],
            "returned": len(result["demands"]),
            "demands": result["demands"]
        }, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"查询需求失败: {str(e)}"
        }, ensure_ascii=False, indent=2)


@mcp.tool()
async def trigger_group_buy(
    region: str,
    budget_segment: Optional[str] = None
) -> str:
    """
    手动触发团购通知
    
    当需求达到阈值时，触发团购通知流程，
    通知运营方并获取车商资源。
    
    参数:
        region: 地区（必填）
        budget_segment: 价位段（可选）
    
    返回:
        JSON 格式的团购触发结果
    """
    try:
        # 检查阈值
        result = check_threshold_demands(
            region=region,
            budget_segment=budget_segment,
            threshold=8
        )
        
        triggered = result["triggered_segments"]
        if not triggered:
            return json.dumps({
                "success": False,
                "error": "未达到触发阈值",
                "current_count": sum(s["count"] for s in result["segments"]),
                "threshold": 8
            }, ensure_ascii=False, indent=2)
        
        # 获取触发团购的需求列表
        segment = triggered[0]
        demand_ids = [d["demand_id"] for d in segment.get("demands", [])]
        
        # 标记为已触发
        mark_demand_as_group_buy_triggered(demand_ids)
        
        # 生成通知内容
        notification = {
            "title": f"🎉 团购触发通知 - {region}{budget_segment or ''}价位段",
            "region": segment["region"],
            "budget_segment": segment["budget_segment"],
            "demand_count": segment["count"],
            "brand_preferences": segment["brand_stats"],
            "type_preferences": segment["type_stats"],
            "demand_ids": demand_ids
        }
        
        return json.dumps({
            "success": True,
            "message": "团购已触发，请通知运营方",
            "notification": notification,
            "demand_ids": demand_ids
        }, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"触发团购失败: {str(e)}"
        }, ensure_ascii=False, indent=2)


@mcp.tool()
async def cleanup_demands() -> str:
    """
    清理过期需求
    
    将超过7天有效期的待匹配需求标记为已过期。
    
    返回:
        JSON 格式的清理结果
    """
    try:
        count = cleanup_expired_demands()
        
        return json.dumps({
            "success": True,
            "message": f"已清理 {count} 条过期需求",
            "cleaned_count": count
        }, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"清理失败: {str(e)}"
        }, ensure_ascii=False, indent=2)


@mcp.tool()
async def get_demand_statistics_summary() -> str:
    """
    获取需求库统计概览
    
    返回需求库的整体统计信息，包括：
    - 总需求数量
    - 按状态分布
    - 按价位段分布
    """
    try:
        stats = get_demand_statistics()
        
        return json.dumps({
            "success": True,
            "statistics": stats
        }, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"获取统计失败: {str(e)}"
        }, ensure_ascii=False, indent=2)


# ============ 启动服务器 ============

if __name__ == "__main__":
    # 支持通过命令行参数指定传输方式
    import sys
    
    transport = "stdio"  # 默认使用标准输入输出
    if len(sys.argv) > 1:
        transport = sys.argv[1]
    
    # 使用 FastMCP 运行
    mcp.run(transport=transport)
