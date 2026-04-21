#!/usr/bin/env python3
"""
二手车 MCP 服务器 - 启动脚本

支持多种启动模式：
1. MCP Server 模式（stdio）- 与 AI 应用通信
2. HTTP API 模式 - 提供 REST API 给车商

Usage:
    python run.py                    # 默认启动 MCP Server
    python run.py mcp                # MCP Server 模式
    python run.py api                # HTTP API 模式
    python run.py both               # 同时启动两种服务
    python run.py init               # 初始化数据库
"""

import sys
import argparse
import subprocess
import time
from pathlib import Path


def init_database():
    """初始化数据库"""
    print("🔧 初始化数据库...")
    try:
        from database import init_database as db_init
        db_init()
        print("✅ 数据库初始化完成")
        return True
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        return False


def start_mcp_server():
    """启动 MCP Server"""
    print("🚀 启动 MCP Server (stdio 模式)...")
    print("   按 Ctrl+C 停止\n")
    
    try:
        import server
        server.mcp.run(transport="stdio")
    except KeyboardInterrupt:
        print("\n👋 MCP Server 已停止")
    except Exception as e:
        print(f"❌ MCP Server 启动失败: {e}")
        return False
    
    return True


def start_api_server():
    """启动 HTTP API Server"""
    import os
    port = int(os.environ.get("PORT", 8000))
    
    print("🚀 启动 HTTP API Server...")
    print(f"   文档地址: http://localhost:{port}/docs\n")
    
    try:
        import uvicorn
        from api import app
        
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
    except KeyboardInterrupt:
        print("\n👋 API Server 已停止")
    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        print("   请运行: pip install -r requirements.txt")
        return False
    except Exception as e:
        print(f"❌ API Server 启动失败: {e}")
        return False
    
    return True


def start_both():
    """同时启动 MCP Server 和 API Server"""
    import multiprocessing
    
    print("🚀 同时启动 MCP Server 和 API Server...\n")
    
    # 使用两个进程分别启动
    mcp_process = multiprocessing.Process(target=start_mcp_server)
    api_process = multiprocessing.Process(target=start_api_server)
    
    try:
        mcp_process.start()
        print(f"   MCP Server 进程 PID: {mcp_process.pid}")
        
        time.sleep(1)
        
        api_process.start()
        print(f"   API Server 进程 PID: {api_process.pid}")
        print(f"   文档地址: http://localhost:8000/docs\n")
        
        print("按 Ctrl+C 停止所有服务\n")
        
        # 等待
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\n👋 正在停止所有服务...")
        if mcp_process.is_alive():
            mcp_process.terminate()
        if api_process.is_alive():
            api_process.terminate()
        print("✅ 所有服务已停止")


def main():
    parser = argparse.ArgumentParser(
        description="二手车 MCP 服务器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run.py              # 启动 MCP Server
  python run.py api          # 启动 API Server
  python run.py both         # 同时启动两个服务
  python run.py init         # 初始化数据库
        """
    )
    
    parser.add_argument(
        "mode",
        nargs="?",
        choices=["mcp", "api", "both", "init"],
        default="mcp",
        help="启动模式 (默认: mcp)"
    )
    
    args = parser.parse_args()
    
    # 确保目录存在
    Path("./data").mkdir(exist_ok=True)
    Path("./logs").mkdir(exist_ok=True)
    
    if args.mode == "init":
        init_database()
    elif args.mode == "mcp":
        start_mcp_server()
    elif args.mode == "api":
        start_api_server()
    elif args.mode == "both":
        start_both()


if __name__ == "__main__":
    main()
