#!/usr/bin/env python3
"""
测试SSE MCP服务器连接的脚本
"""

import asyncio
import sys
import logging
from pathlib import Path

# 添加tinyagent模块到路径
sys.path.insert(0, str(Path(__file__).parent))

try:
    from agents.mcp import MCPServerSse
    print("✓ OpenAI Agents SDK 导入成功")
except ImportError as e:
    print(f"✗ OpenAI Agents SDK 导入失败: {e}")
    sys.exit(1)

async def test_sse_server():
    """测试SSE服务器连接"""
    
    print("📡 测试SSE MCP服务器连接...")
    
    # 创建SSE服务器配置
    server = MCPServerSse(
        name="test-sse",
        params={
            "url": "http://localhost:8081/sse",
            "timeout": 5,
            "sse_read_timeout": 10
        }
    )
    
    try:
        print("🔌 尝试连接SSE服务器...")
        async with server as connected_server:
            print("✓ SSE服务器连接成功！")
            
            # 尝试列出工具
            print("🔍 获取工具列表...")
            tools = await connected_server.list_tools()
            print(f"✓ 发现 {len(tools)} 个工具:")
            for tool in tools:
                print(f"  - {tool.name}: {tool.description}")
                
            return True
            
    except Exception as e:
        print(f"✗ SSE服务器连接失败: {e}")
        return False

async def test_stdio_servers():
    """测试stdio服务器"""
    
    print("\n📁 测试stdio MCP服务器...")
    
    try:
        from agents.mcp import MCPServerStdio
        
        # 测试filesystem服务器
        fs_server = MCPServerStdio(
            name="test-filesystem",
            params={
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "."]
            }
        )
        
        print("🔌 尝试连接filesystem服务器...")
        async with fs_server as connected_fs:
            print("✓ Filesystem服务器连接成功！")
            
            tools = await connected_fs.list_tools()
            print(f"✓ Filesystem发现 {len(tools)} 个工具")
            
        return True
        
    except Exception as e:
        print(f"✗ Stdio服务器测试失败: {e}")
        return False

async def main():
    """主测试函数"""
    
    print("🧪 TinyAgent MCP 服务器连接测试")
    print("=" * 50)
    
    # 设置日志级别
    logging.basicConfig(level=logging.WARNING)
    
    # 测试stdio服务器
    stdio_success = await test_stdio_servers()
    
    # 测试SSE服务器  
    sse_success = await test_sse_server()
    
    print("\n" + "=" * 50)
    print("📊 测试结果总结:")
    print(f"  - Stdio服务器: {'✓ 成功' if stdio_success else '✗ 失败'}")
    print(f"  - SSE服务器: {'✓ 成功' if sse_success else '✗ 失败'}")
    
    if not sse_success:
        print("\n💡 SSE服务器连接失败可能的原因:")
        print("  1. 服务器未运行在 http://localhost:8081")
        print("  2. 服务器配置错误")
        print("  3. 防火墙阻止连接")
        print("  4. 服务器返回502 Bad Gateway")
        print("\n🔧 请按以下步骤启动SSE服务器:")
        print("  1. cd C:\\work\\github\\mcp\\mcp-sse-client-server")
        print("  2. python mcp-server-search.py")
        print("  3. 确保服务器监听在 localhost:8081")

if __name__ == "__main__":
    asyncio.run(main()) 