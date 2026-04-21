"""
二手车 MCP 服务器 - 数据库操作模块

提供车源数据和车商数据的持久化存储
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

# 数据库路径
DB_PATH = Path(__file__).parent / "data" / "car_inventory.db"
DB_PATH.parent.mkdir(exist_ok=True)


def get_connection() -> sqlite3.Connection:
    """获取数据库连接"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_cursor():
    """上下文管理器，自动管理数据库连接"""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        yield cursor
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def init_database():
    """初始化数据库表结构"""
    
    # 车商表
    DEALER_TABLE = """
    CREATE TABLE IF NOT EXISTS dealers (
        dealer_id TEXT PRIMARY KEY,
        dealer_name TEXT NOT NULL,
        dealer_type TEXT DEFAULT 'personal',  -- personal, dealer, enterprise
        api_key TEXT UNIQUE NOT NULL,
        api_secret TEXT,
        phone TEXT,
        email TEXT,
        region TEXT,
        city TEXT,
        address TEXT,
        rating REAL DEFAULT 0.0,
        status TEXT DEFAULT 'active',  -- active, suspended, inactive
        created_at TEXT DEFAULT (datetime('now', 'localtime')),
        updated_at TEXT DEFAULT (datetime('now', 'localtime'))
    )
    """
    
    # 车源表
    CAR_TABLE = """
    CREATE TABLE IF NOT EXISTS cars (
        car_id TEXT PRIMARY KEY,
        dealer_id TEXT NOT NULL,
        brand TEXT NOT NULL,
        series TEXT,
        model TEXT NOT NULL,
        price REAL NOT NULL,
        original_price REAL,
        discount_rate REAL,
        year INTEGER,
        month INTEGER,
        mileage REAL,
        car_type TEXT,
        seats INTEGER,
        fuel_type TEXT,
        transmission TEXT,
        emission_standard TEXT,
        color TEXT,
        region TEXT,
        city TEXT,
        address TEXT,
        condition TEXT,
        warranty TEXT,
        tags TEXT,  -- JSON array stored as string
        images TEXT,  -- JSON array stored as string
        source TEXT DEFAULT 'dealer_upload',
        status TEXT DEFAULT 'available',  -- available, reserved, sold, expired
        created_at TEXT DEFAULT (datetime('now', 'localtime')),
        updated_at TEXT DEFAULT (datetime('now', 'localtime')),
        FOREIGN KEY (dealer_id) REFERENCES dealers(dealer_id)
    )
    """
    
    # 创建索引
    CAR_INDEXES = [
        "CREATE INDEX IF NOT EXISTS idx_cars_dealer ON cars(dealer_id)",
        "CREATE INDEX IF NOT EXISTS idx_cars_region ON cars(region)",
        "CREATE INDEX IF NOT EXISTS idx_cars_city ON cars(city)",
        "CREATE INDEX IF NOT EXISTS idx_cars_brand ON cars(brand)",
        "CREATE INDEX IF NOT EXISTS idx_cars_price ON cars(price)",
        "CREATE INDEX IF NOT EXISTS idx_cars_status ON cars(status)",
        "CREATE INDEX IF NOT EXISTS idx_cars_car_type ON cars(car_type)",
        "CREATE INDEX IF NOT EXISTS idx_cars_fuel_type ON cars(fuel_type)",
    ]
    
    # 需求表（用于需求库）
    DEMAND_TABLE = """
    CREATE TABLE IF NOT EXISTS demands (
        demand_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        user_nickname TEXT,
        preferences TEXT NOT NULL,  -- JSON object stored as string
        budget_segment TEXT,
        status TEXT DEFAULT 'pending',  -- pending, matched, group_buy_triggered, expired, cancelled
        created_at TEXT DEFAULT (datetime('now', 'localtime')),
        expires_at TEXT NOT NULL,
        matched_count INTEGER DEFAULT 0,
        last_matched_at TEXT,
        notes TEXT,
        updated_at TEXT DEFAULT (datetime('now', 'localtime'))
    )
    """
    
    # 需求表索引
    DEMAND_INDEXES = [
        "CREATE INDEX IF NOT EXISTS idx_demands_status ON demands(status)",
        "CREATE INDEX IF NOT EXISTS idx_demands_user ON demands(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_demands_expires ON demands(expires_at)",
        "CREATE INDEX IF NOT EXISTS idx_demands_region ON demands(user_id)",
    ]
    
    with get_cursor() as cursor:
        cursor.execute(DEALER_TABLE)
        cursor.execute(CAR_TABLE)
        for index_sql in CAR_INDEXES:
            cursor.execute(index_sql)
        cursor.execute(DEMAND_TABLE)
        for index_sql in DEMAND_INDEXES:
            cursor.execute(index_sql)


# ============ 车商操作 ============

def create_dealer(dealer_data: Dict[str, Any]) -> str:
    """创建车商"""
    import secrets
    import hashlib
    
    dealer_id = dealer_data.get("dealer_id") or f"DEALER_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    api_key = secrets.token_urlsafe(32)
    
    # 生成 API Secret (用于签名验证)
    secret_raw = f"{dealer_id}:{datetime.now().isoformat()}"
    api_secret = hashlib.sha256(secret_raw.encode()).hexdigest()[:32]
    
    with get_cursor() as cursor:
        cursor.execute("""
            INSERT INTO dealers (
                dealer_id, dealer_name, dealer_type, api_key, api_secret,
                phone, email, region, city, address, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            dealer_id,
            dealer_data.get("dealer_name"),
            dealer_data.get("dealer_type", "personal"),
            api_key,
            api_secret,
            dealer_data.get("phone"),
            dealer_data.get("email"),
            dealer_data.get("region"),
            dealer_data.get("city"),
            dealer_data.get("address"),
            dealer_data.get("status", "active")
        ))
    
    return dealer_id


def verify_api_key(api_key: str) -> Optional[Dict[str, Any]]:
    """验证 API Key 并返回车商信息"""
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT * FROM dealers 
            WHERE api_key = ? AND status = 'active'
        """, (api_key,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_dealer(dealer_id: str) -> Optional[Dict[str, Any]]:
    """获取车商信息"""
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM dealers WHERE dealer_id = ?", (dealer_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def list_dealers(region: Optional[str] = None, status: str = "active") -> List[Dict[str, Any]]:
    """获取车商列表"""
    with get_cursor() as cursor:
        if region:
            cursor.execute("""
                SELECT * FROM dealers 
                WHERE region LIKE ? AND status = ?
                ORDER BY rating DESC
            """, (f"%{region}%", status))
        else:
            cursor.execute("""
                SELECT * FROM dealers 
                WHERE status = ?
                ORDER BY rating DESC
            """, (status,))
        return [dict(row) for row in cursor.fetchall()]


# ============ 车源操作 ============

def create_car(car_data: Dict[str, Any]) -> str:
    """创建车源"""
    import json
    
    car_id = car_data.get("car_id") or f"CAR_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    
    # 处理 JSON 字段
    tags = car_data.get("tags")
    if isinstance(tags, list):
        tags = json.dumps(tags, ensure_ascii=False)
    
    images = car_data.get("images")
    if isinstance(images, list):
        images = json.dumps(images, ensure_ascii=False)
    
    # 计算折扣率
    price = car_data.get("price", 0)
    original_price = car_data.get("original_price")
    if original_price and original_price > 0:
        discount_rate = round(price / original_price, 2)
    else:
        discount_rate = None
    
    with get_cursor() as cursor:
        cursor.execute("""
            INSERT INTO cars (
                car_id, dealer_id, brand, series, model, price, original_price,
                discount_rate, year, month, mileage, car_type, seats, fuel_type,
                transmission, emission_standard, color, region, city, address,
                condition, warranty, tags, images, source, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            car_id,
            car_data.get("dealer_id"),
            car_data.get("brand"),
            car_data.get("series"),
            car_data.get("model"),
            price,
            original_price,
            discount_rate,
            car_data.get("year"),
            car_data.get("month"),
            car_data.get("mileage"),
            car_data.get("car_type"),
            car_data.get("seats"),
            car_data.get("fuel_type"),
            car_data.get("transmission"),
            car_data.get("emission_standard"),
            car_data.get("color"),
            car_data.get("region"),
            car_data.get("city"),
            car_data.get("address"),
            car_data.get("condition"),
            car_data.get("warranty"),
            tags,
            images,
            car_data.get("source", "dealer_upload"),
            car_data.get("status", "available")
        ))
    
    return car_id


def batch_create_cars(cars_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """批量创建车源"""
    import json
    
    success_count = 0
    error_count = 0
    errors = []
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        for car_data in cars_data:
            try:
                car_id = car_data.get("car_id") or f"CAR_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
                
                tags = car_data.get("tags")
                if isinstance(tags, list):
                    tags = json.dumps(tags, ensure_ascii=False)
                
                images = car_data.get("images")
                if isinstance(images, list):
                    images = json.dumps(images, ensure_ascii=False)
                
                price = car_data.get("price", 0)
                original_price = car_data.get("original_price")
                if original_price and original_price > 0:
                    discount_rate = round(price / original_price, 2)
                else:
                    discount_rate = None
                
                cursor.execute("""
                    INSERT INTO cars (
                        car_id, dealer_id, brand, series, model, price, original_price,
                        discount_rate, year, month, mileage, car_type, seats, fuel_type,
                        transmission, emission_standard, color, region, city, address,
                        condition, warranty, tags, images, source, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    car_id,
                    car_data.get("dealer_id"),
                    car_data.get("brand"),
                    car_data.get("series"),
                    car_data.get("model"),
                    price,
                    original_price,
                    discount_rate,
                    car_data.get("year"),
                    car_data.get("month"),
                    car_data.get("mileage"),
                    car_data.get("car_type"),
                    car_data.get("seats"),
                    car_data.get("fuel_type"),
                    car_data.get("transmission"),
                    car_data.get("emission_standard"),
                    car_data.get("color"),
                    car_data.get("region"),
                    car_data.get("city"),
                    car_data.get("address"),
                    car_data.get("condition"),
                    car_data.get("warranty"),
                    tags,
                    images,
                    car_data.get("source", "dealer_upload"),
                    car_data.get("status", "available")
                ))
                success_count += 1
                
            except Exception as e:
                error_count += 1
                errors.append({
                    "car_id": car_data.get("car_id"),
                    "error": str(e)
                })
        
        conn.commit()
    
    return {
        "success_count": success_count,
        "error_count": error_count,
        "errors": errors
    }


def get_car(car_id: str) -> Optional[Dict[str, Any]]:
    """获取单个车源"""
    import json
    
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM cars WHERE car_id = ?", (car_id,))
        row = cursor.fetchone()
        if not row:
            return None
        
        car = dict(row)
        
        # 解析 JSON 字段
        if car.get("tags"):
            try:
                car["tags"] = json.loads(car["tags"])
            except:
                car["tags"] = []
        
        if car.get("images"):
            try:
                car["images"] = json.loads(car["images"])
            except:
                car["images"] = []
        
        return car


def update_car(car_id: str, car_data: Dict[str, Any]) -> bool:
    """更新车源"""
    import json
    
    # 构建更新字段
    fields = []
    values = []
    
    for key in ["brand", "series", "model", "price", "original_price", "year", 
                "month", "mileage", "car_type", "seats", "fuel_type", "transmission",
                "emission_standard", "color", "region", "city", "address", 
                "condition", "warranty", "source", "status"]:
        if key in car_data:
            fields.append(f"{key} = ?")
            values.append(car_data[key])
    
    # 处理 JSON 字段
    if "tags" in car_data:
        fields.append("tags = ?")
        values.append(json.dumps(car_data["tags"], ensure_ascii=False) if isinstance(car_data["tags"], list) else car_data["tags"])
    
    if "images" in car_data:
        fields.append("images = ?")
        values.append(json.dumps(car_data["images"], ensure_ascii=False) if isinstance(car_data["images"], list) else car_data["images"])
    
    if not fields:
        return False
    
    fields.append("updated_at = datetime('now', 'localtime')")
    values.append(car_id)
    
    with get_cursor() as cursor:
        cursor.execute(f"""
            UPDATE cars SET {', '.join(fields)} WHERE car_id = ?
        """, values)
        return cursor.rowcount > 0


def delete_car(car_id: str) -> bool:
    """删除车源（软删除，标记为已过期）"""
    return update_car(car_id, {"status": "expired"})


def list_cars(
    dealer_id: Optional[str] = None,
    region: Optional[str] = None,
    city: Optional[str] = None,
    brand: Optional[str] = None,
    car_type: Optional[str] = None,
    fuel_type: Optional[str] = None,
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    year_min: Optional[int] = None,
    status: str = "available",
    limit: int = 50,
    offset: int = 0
) -> Dict[str, Any]:
    """查询车源列表（支持多种筛选条件）"""
    import json
    
    conditions = ["status = ?"]
    params = [status]
    
    if dealer_id:
        conditions.append("dealer_id = ?")
        params.append(dealer_id)
    
    if region:
        conditions.append("region LIKE ?")
        params.append(f"%{region}%")
    
    if city:
        conditions.append("city LIKE ?")
        params.append(f"%{city}%")
    
    if brand:
        conditions.append("brand LIKE ?")
        params.append(f"%{brand}%")
    
    if car_type:
        conditions.append("car_type = ?")
        params.append(car_type)
    
    if fuel_type:
        conditions.append("fuel_type = ?")
        params.append(fuel_type)
    
    if price_min is not None:
        conditions.append("price >= ?")
        params.append(price_min)
    
    if price_max is not None:
        conditions.append("price <= ?")
        params.append(price_max)
    
    if year_min:
        conditions.append("year >= ?")
        params.append(year_min)
    
    where_clause = " AND ".join(conditions)
    
    with get_cursor() as cursor:
        # 获取总数
        cursor.execute(f"SELECT COUNT(*) as total FROM cars WHERE {where_clause}", params)
        total = cursor.fetchone()["total"]
        
        # 获取分页数据
        cursor.execute(f"""
            SELECT * FROM cars 
            WHERE {where_clause}
            ORDER BY updated_at DESC
            LIMIT ? OFFSET ?
        """, params + [limit, offset])
        
        cars = []
        for row in cursor.fetchall():
            car = dict(row)
            # 解析 JSON 字段
            if car.get("tags"):
                try:
                    car["tags"] = json.loads(car["tags"])
                except:
                    car["tags"] = []
            if car.get("images"):
                try:
                    car["images"] = json.loads(car["images"])
                except:
                    car["images"] = []
            cars.append(car)
        
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "cars": cars
        }


def get_car_statistics(dealer_id: Optional[str] = None) -> Dict[str, Any]:
    """获取车源统计信息"""
    with get_cursor() as cursor:
        base_where = f"WHERE dealer_id = '{dealer_id}'" if dealer_id else ""
        
        # 总数
        cursor.execute(f"SELECT COUNT(*) as count FROM cars {base_where}")
        total = cursor.fetchone()["count"]
        
        # 按状态统计
        cursor.execute(f"""
            SELECT status, COUNT(*) as count 
            FROM cars {base_where}
            GROUP BY status
        """)
        by_status = {row["status"]: row["count"] for row in cursor.fetchall()}
        
        # 按品牌统计
        cursor.execute(f"""
            SELECT brand, COUNT(*) as count 
            FROM cars {base_where} AND status = 'available'
            GROUP BY brand
            ORDER BY count DESC
            LIMIT 10
        """)
        by_brand = [{"brand": row["brand"], "count": row["count"]} for row in cursor.fetchall()]
        
        # 价格区间统计
        cursor.execute(f"""
            SELECT 
                CASE 
                    WHEN price < 5 THEN '<5万'
                    WHEN price >= 5 AND price < 10 THEN '5-10万'
                    WHEN price >= 10 AND price < 20 THEN '10-20万'
                    WHEN price >= 20 AND price < 30 THEN '20-30万'
                    WHEN price >= 30 AND price < 50 THEN '30-50万'
                    ELSE '50万+'
                END as price_range,
                COUNT(*) as count
            FROM cars {base_where} AND status = 'available'
            GROUP BY price_range
        """)
        by_price_range = [{"range": row["price_range"], "count": row["count"]} for row in cursor.fetchall()]
        
        return {
            "total": total,
            "by_status": by_status,
            "by_brand": by_brand,
            "by_price_range": by_price_range
        }


# ============ 需求库操作 ============

def generate_demand_id() -> str:
    """生成需求ID"""
    date_str = datetime.now().strftime("%Y%m%d")
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT COUNT(*) as count FROM demands 
            WHERE demand_id LIKE ?
        """, (f"DM{date_str}%",))
        count = cursor.fetchone()["count"]
    return f"DM{date_str}{str(count + 1).zfill(3)}"


def get_budget_segment(budget_min: float, budget_max: float) -> str:
    """根据预算范围获取价位段名称"""
    if budget_max <= 5:
        return "5万以内"
    elif budget_min >= 5 and budget_max <= 10:
        return "5-10万"
    elif budget_min >= 10 and budget_max <= 15:
        return "10-15万"
    elif budget_min >= 15 and budget_max <= 20:
        return "15-20万"
    elif budget_min >= 20 and budget_max <= 30:
        return "20-30万"
    else:
        return "30万以上"


def create_demand(demand_data: Dict[str, Any]) -> str:
    """创建需求"""
    import json
    from datetime import timedelta
    
    demand_id = demand_data.get("demand_id") or generate_demand_id()
    preferences = demand_data.get("preferences", {})
    
    # 计算价位段
    budget_min = preferences.get("budget_min", 0)
    budget_max = preferences.get("budget_max", 999)
    budget_segment = demand_data.get("budget_segment") or get_budget_segment(budget_min, budget_max)
    
    # 计算过期时间（7天后）
    now = datetime.now()
    expires_at = demand_data.get("expires_at") or (now + timedelta(days=7)).isoformat()
    
    with get_cursor() as cursor:
        cursor.execute("""
            INSERT INTO demands (
                demand_id, user_id, user_nickname, preferences, budget_segment,
                status, created_at, expires_at, matched_count, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            demand_id,
            demand_data.get("user_id"),
            demand_data.get("user_nickname"),
            json.dumps(preferences, ensure_ascii=False),
            budget_segment,
            demand_data.get("status", "pending"),
            now.isoformat(),
            expires_at,
            demand_data.get("matched_count", 0),
            demand_data.get("notes", "")
        ))
    
    return demand_id


def get_demand(demand_id: str) -> Optional[Dict[str, Any]]:
    """获取单个需求"""
    import json
    
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM demands WHERE demand_id = ?", (demand_id,))
        row = cursor.fetchone()
        if not row:
            return None
        
        demand = dict(row)
        if demand.get("preferences"):
            try:
                demand["preferences"] = json.loads(demand["preferences"])
            except:
                demand["preferences"] = {}
        
        return demand


def update_demand(demand_id: str, demand_data: Dict[str, Any]) -> bool:
    """更新需求"""
    import json
    
    fields = []
    values = []
    
    for key in ["user_nickname", "status", "notes"]:
        if key in demand_data:
            fields.append(f"{key} = ?")
            values.append(demand_data[key])
    
    # 处理 preferences JSON
    if "preferences" in demand_data:
        fields.append("preferences = ?")
        values.append(json.dumps(demand_data["preferences"], ensure_ascii=False))
    
    if "budget_segment" in demand_data:
        fields.append("budget_segment = ?")
        values.append(demand_data["budget_segment"])
    
    if "matched_count" in demand_data:
        fields.append("matched_count = ?")
        values.append(demand_data["matched_count"])
    
    if "last_matched_at" in demand_data:
        fields.append("last_matched_at = ?")
        values.append(demand_data["last_matched_at"])
    
    if not fields:
        return False
    
    fields.append("updated_at = datetime('now', 'localtime')")
    values.append(demand_id)
    
    with get_cursor() as cursor:
        cursor.execute(f"""
            UPDATE demands SET {', '.join(fields)} WHERE demand_id = ?
        """, values)
        return cursor.rowcount > 0


def delete_demand(demand_id: str) -> bool:
    """删除需求"""
    return update_demand(demand_id, {"status": "cancelled"})


def list_demands(
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    region: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> Dict[str, Any]:
    """查询需求列表"""
    import json
    
    conditions = ["1=1"]
    params = []
    
    if user_id:
        conditions.append("user_id = ?")
        params.append(user_id)
    
    if status:
        conditions.append("status = ?")
        params.append(status)
    
    where_clause = " AND ".join(conditions)
    
    with get_cursor() as cursor:
        # 获取总数
        cursor.execute(f"SELECT COUNT(*) as total FROM demands WHERE {where_clause}", params)
        total = cursor.fetchone()["total"]
        
        # 获取分页数据
        cursor.execute(f"""
            SELECT * FROM demands 
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, params + [limit, offset])
        
        demands = []
        for row in cursor.fetchall():
            demand = dict(row)
            if demand.get("preferences"):
                try:
                    demand["preferences"] = json.loads(demand["preferences"])
                except:
                    demand["preferences"] = {}
            demands.append(demand)
        
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "demands": demands
        }


def check_threshold_demands(
    region: Optional[str] = None,
    budget_segment: Optional[str] = None,
    threshold: int = 8
) -> Dict[str, Any]:
    """检查指定地区和价位段的需求是否达到阈值（加权计算版本）
    
    所有 pending 状态的需求都参与计算，无论是否过期。
    按创建时间分层赋予不同权重。
    """
    import json
    
    conditions = ["status = 'pending'"]
    params = []
    
    if region:
        # 从 preferences 中提取 region 查询
        conditions.append("preferences LIKE ?")
        params.append(f"%\"region\": \"%{region}%\"%")
    
    if budget_segment:
        conditions.append("budget_segment = ?")
        params.append(budget_segment)
    
    where_clause = " AND ".join(conditions)
    
    with get_cursor() as cursor:
        # 获取所有 pending 需求
        cursor.execute(f"""
            SELECT * FROM demands 
            WHERE {where_clause}
            ORDER BY created_at DESC
        """, params)
        
        demands = []
        for row in cursor.fetchall():
            demand = dict(row)
            if demand.get("preferences"):
                try:
                    demand["preferences"] = json.loads(demand["preferences"])
                except:
                    demand["preferences"] = {}
            demands.append(demand)
        
        # 按地区+价位段聚合
        segments = {}
        for demand in demands:
            pref = demand.get("preferences", {})
            r = pref.get("region", "未知")
            seg = demand.get("budget_segment", "未知")
            key = (r, seg)
            
            if key not in segments:
                segments[key] = {
                    "region": r,
                    "budget_segment": seg,
                    "count": 0,
                    "demands": [],
                    "brand_stats": {},
                    "type_stats": {},
                    "tier_stats": {
                        "active": {"count": 0, "weight": 1.0, "total": 0.0},
                        "stale": {"count": 0, "weight": 0.8, "total": 0.0},
                        "old": {"count": 0, "weight": 0.6, "total": 0.0},
                        "aging": {"count": 0, "weight": 0.4, "total": 0.0},
                        "archived": {"count": 0, "weight": 0.2, "total": 0.0},
                    }
                }
            
            segments[key]["count"] += 1
            segments[key]["demands"].append(demand)
            
            # 计算时间分层权重
            time_status, weight = _get_demand_time_status(demand.get("created_at"))
            if time_status in segments[key]["tier_stats"]:
                segments[key]["tier_stats"][time_status]["count"] += 1
                segments[key]["tier_stats"][time_status]["total"] += weight
            
            # 统计品牌和车型偏好
            for brand in pref.get("brands", []):
                segments[key]["brand_stats"][brand] = segments[key]["brand_stats"].get(brand, 0) + 1
            for car_type in pref.get("car_types", []):
                segments[key]["type_stats"][car_type] = segments[key]["type_stats"].get(car_type, 0) + 1
        
        # 计算加权分数并筛选达到阈值的组合
        triggered_segments = []
        all_segments = []
        
        for key, v in segments.items():
            # 计算加权总分
            weighted_score = sum(t["total"] for t in v["tier_stats"].values())
            
            segment_info = {
                "region": v["region"],
                "budget_segment": v["budget_segment"],
                "count": v["count"],
                "weighted_score": round(weighted_score, 2),
                "threshold": threshold,
                "triggered": weighted_score >= threshold,
                "brand_stats": v["brand_stats"],
                "type_stats": v["type_stats"],
                "tier_stats": v["tier_stats"],
                "demands": v["demands"]
            }
            
            all_segments.append(segment_info)
            if weighted_score >= threshold:
                triggered_segments.append(segment_info)
        
        return {
            "threshold": threshold,
            "total_pending": len(demands),
            "segments": all_segments,
            "triggered_segments": triggered_segments
        }


def _get_demand_time_status(created_at: str) -> tuple:
    """根据创建时间获取需求的时间分层状态和权重
    
    Returns:
        Tuple[str, float]: (时间状态, 权重)
    """
    try:
        if isinstance(created_at, str):
            created_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        else:
            created_time = created_at
    except (ValueError, TypeError):
        return "active", 1.0
    
    # 统一使用本地时间比较
    if created_time.tzinfo is not None:
        created_time = created_time.replace(tzinfo=None)
    days_diff = (datetime.now() - created_time).days
    
    # 根据天数差确定状态和权重
    if days_diff <= 14:
        return "active", 1.0
    elif days_diff <= 90:
        return "stale", 0.8
    elif days_diff <= 180:
        return "old", 0.6
    elif days_diff <= 365:
        return "aging", 0.4
    else:
        return "archived", 0.2


def mark_demand_as_matched(demand_id: str) -> bool:
    """标记需求为已匹配"""
    demand = get_demand(demand_id)
    if not demand:
        return False
    
    matched_count = demand.get("matched_count", 0) + 1
    return update_demand(demand_id, {
        "matched_count": matched_count,
        "last_matched_at": datetime.now().isoformat(),
        "status": "matched"
    })


def mark_demand_as_group_buy_triggered(demand_ids: List[str]) -> bool:
    """批量标记需求为已触发团购"""
    for demand_id in demand_ids:
        update_demand(demand_id, {"status": "group_buy_triggered"})
    return True


def cleanup_expired_demands() -> int:
    """清理过期需求，返回清理数量"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with get_cursor() as cursor:
        cursor.execute("""
            UPDATE demands 
            SET status = 'expired', updated_at = datetime('now', 'localtime')
            WHERE status = 'pending' AND expires_at < ?
        """, (now,))
        
        return cursor.rowcount


def get_demand_statistics() -> Dict[str, Any]:
    """获取需求统计信息"""
    with get_cursor() as cursor:
        # 总数
        cursor.execute("SELECT COUNT(*) as count FROM demands")
        total = cursor.fetchone()["count"]
        
        # 按状态统计
        cursor.execute("""
            SELECT status, COUNT(*) as count 
            FROM demands
            GROUP BY status
        """)
        by_status = {row["status"]: row["count"] for row in cursor.fetchall()}
        
        # 按价位段统计
        cursor.execute("""
            SELECT budget_segment, COUNT(*) as count 
            FROM demands
            WHERE status = 'pending'
            GROUP BY budget_segment
            ORDER BY count DESC
        """)
        by_segment = [{"segment": row["budget_segment"], "count": row["count"]} for row in cursor.fetchall()]
        
        return {
            "total": total,
            "by_status": by_status,
            "pending_by_segment": by_segment
        }


# 初始化数据库
init_database()
