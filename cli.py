"""
二手车 MCP 服务器 - 工具脚本

提供命令行工具用于管理车源数据
"""

import argparse
import json
import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.database import (
    init_database,
    create_dealer,
    list_dealers,
    create_car,
    batch_create_cars,
    list_cars,
    get_car,
    get_car_statistics
)
from scripts.data_loader import load_cars_from_excel


def cmd_register_dealer(args):
    """注册车商"""
    dealer_data = {
        "dealer_name": args.name,
        "dealer_type": args.type or "personal",
        "phone": args.phone,
        "email": args.email,
        "region": args.region,
        "city": args.city,
    }
    
    dealer_id = create_dealer(dealer_data)
    
    # 获取完整信息
    from mcp.database import get_dealer
    dealer = get_dealer(dealer_id)
    
    print("\n✅ 车商注册成功！")
    print(f"\n车商ID: {dealer['dealer_id']}")
    print(f"API Key: {dealer['api_key']}")
    print(f"API Secret: {dealer['api_secret']}")
    print("\n⚠️ 请妥善保管 API Key 和 API Secret！")


def cmd_list_dealers(args):
    """列出车商"""
    dealers = list_dealers(region=args.region, status=args.status)
    
    if not dealers:
        print("没有找到车商")
        return
    
    print(f"\n找到 {len(dealers)} 个车商：\n")
    for d in dealers:
        print(f"  {d['dealer_id']} | {d['dealer_name']} | {d['region']} | {d['status']}")


def cmd_import_excel(args):
    """从 Excel 导入车源"""
    if not Path(args.file).exists():
        print(f"❌ 文件不存在: {args.file}")
        return
    
    # 读取 Excel
    cars = load_cars_from_excel(args.file)
    
    if not cars:
        print("❌ 未从文件中读取到数据")
        return
    
    print(f"📖 从 {args.file} 读取了 {len(cars)} 条数据")
    
    # 添加 dealer_id
    for car in cars:
        car["dealer_id"] = args.dealer_id
    
    # 批量导入
    result = batch_create_cars(cars)
    
    print(f"\n✅ 导入完成")
    print(f"   成功: {result['success_count']}")
    print(f"   失败: {result['error_count']}")
    
    if result['errors']:
        print("\n错误详情：")
        for err in result['errors'][:10]:
            print(f"   - {err['car_id']}: {err['error']}")


def cmd_create_car(args):
    """创建单个车源"""
    car_data = {
        "dealer_id": args.dealer_id,
        "brand": args.brand,
        "model": args.model,
        "price": args.price,
        "year": args.year,
        "mileage": args.mileage,
        "region": args.region,
        "city": args.city,
    }
    
    car_id = create_car(car_data)
    print(f"✅ 车源创建成功: {car_id}")


def cmd_list_cars(args):
    """列出车源"""
    result = list_cars(
        dealer_id=args.dealer_id,
        region=args.region,
        brand=args.brand,
        price_min=args.price_min,
        price_max=args.price_max,
        limit=args.limit
    )
    
    print(f"\n找到 {result['total']} 辆车源（显示 {len(result['cars'])} 辆）：\n")
    
    for car in result['cars']:
        print(f"  {car['car_id']} | {car['brand']} {car['model']} | {car['price']}万 | {car.get('region', '')}")


def cmd_get_car(args):
    """获取车源详情"""
    car = get_car(args.car_id)
    
    if not car:
        print(f"❌ 未找到车源: {args.car_id}")
        return
    
    print(f"\n🚗 {car['brand']} {car['model']}")
    print("-" * 40)
    
    for key, value in car.items():
        if key not in ('tags', 'images') and value is not None:
            print(f"  {key}: {value}")


def cmd_stats(args):
    """获取统计信息"""
    stats = get_car_statistics(dealer_id=args.dealer_id)
    
    print("\n📊 车源统计\n")
    print(f"总车源数: {stats['total']}")
    
    if stats.get('by_status'):
        print("\n按状态：")
        for status, count in stats['by_status'].items():
            print(f"  {status}: {count}")
    
    if stats.get('by_brand'):
        print("\n品牌分布（Top 10）：")
        for item in stats['by_brand'][:10]:
            print(f"  {item['brand']}: {item['count']}")


def cmd_init(args):
    """初始化数据库"""
    from mcp.database import init_database
    print("🔧 初始化数据库...")
    init_database()
    print("✅ 初始化完成")


def main():
    parser = argparse.ArgumentParser(description="二手车 MCP 服务器工具")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # 注册车商
    p = subparsers.add_parser("register", help="注册车商")
    p.add_argument("--name", "-n", required=True, help="车商名称")
    p.add_argument("--type", "-t", choices=["personal", "dealer", "enterprise"], help="车商类型")
    p.add_argument("--phone", "-p", help="联系电话")
    p.add_argument("--email", "-e", help="电子邮箱")
    p.add_argument("--region", "-r", help="省份")
    p.add_argument("--city", "-c", help="城市")
    p.set_defaults(func=cmd_register_dealer)
    
    # 列出车商
    p = subparsers.add_parser("dealers", help="列出车商")
    p.add_argument("--region", "-r", help="筛选省份")
    p.add_argument("--status", "-s", default="active", help="状态筛选")
    p.set_defaults(func=cmd_list_dealers)
    
    # 导入 Excel
    p = subparsers.add_parser("import", help="从 Excel 导入车源")
    p.add_argument("--file", "-f", required=True, help="Excel 文件路径")
    p.add_argument("--dealer-id", "-d", required=True, help="车商 ID")
    p.set_defaults(func=cmd_import_excel)
    
    # 创建车源
    p = subparsers.add_parser("create", help="创建车源")
    p.add_argument("--dealer-id", "-d", required=True, help="车商 ID")
    p.add_argument("--brand", "-b", required=True, help="品牌")
    p.add_argument("--model", "-m", required=True, help="车型")
    p.add_argument("--price", "-p", type=float, required=True, help="价格（万元）")
    p.add_argument("--year", "-y", type=int, help="年份")
    p.add_argument("--mileage", default=0, type=float, help="里程（万公里）")
    p.add_argument("--region", "-r", help="省份")
    p.add_argument("--city", "-c", help="城市")
    p.set_defaults(func=cmd_create_car)
    
    # 列出车源
    p = subparsers.add_parser("list", help="列出车源")
    p.add_argument("--dealer-id", "-d", help="车商 ID")
    p.add_argument("--region", "-r", help="省份")
    p.add_argument("--brand", "-b", help="品牌")
    p.add_argument("--price-min", type=float, help="最低价格")
    p.add_argument("--price-max", type=float, help="最高价格")
    p.add_argument("--limit", "-l", type=int, default=50, help="返回数量")
    p.set_defaults(func=cmd_list_cars)
    
    # 获取车源详情
    p = subparsers.add_parser("get", help="获取车源详情")
    p.add_argument("car_id", help="车源 ID")
    p.set_defaults(func=cmd_get_car)
    
    # 统计
    p = subparsers.add_parser("stats", help="获取统计信息")
    p.add_argument("--dealer-id", "-d", help="车商 ID（不填则显示全局）")
    p.set_defaults(func=cmd_stats)
    
    # 初始化
    p = subparsers.add_parser("init", help="初始化数据库")
    p.set_defaults(func=cmd_init)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    args.func(args)


if __name__ == "__main__":
    main()
