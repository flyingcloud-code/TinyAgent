#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试MCP相关问题的专用脚本
解决三个主要问题：
1. MCP服务器连接失败
2. 中文乱码显示 
3. my-search服务器无法连接
"""

import sys
import os
import asyncio
import traceback
import warnings
from pathlib import Path

# 确保正确的Python路径
sys.path.insert(0, str(Path(__file__).parent))

# 设置控制台编码为UTF-8
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'

# 抑制异步清理警告
warnings.filterwarnings("ignore", category=ResourceWarning)
warnings.filterwarnings("ignore", message="Unclosed client session")
warnings.filterwarnings("ignore", message="Unclosed connector")

from tinyagent.core.config import get_config
from tinyagent.core.agent import TinyAgent

async def debug_mcp_issues():
    """调试MCP相关问题"""
    print("🔍 TinyAgent MCP问题调试器 v2.0")
    print("=" * 50)
    
    agent = None
    
    try:
        # 1. 检查配置
        print("\n1. 📋 检查配置...")
        try:
            config = get_config()
            print(f"   ✅ 配置加载成功")
            print(f"   📊 MCP启用状态: {config.mcp.enabled}")
            print(f"   📊 启用的服务器: {config.mcp.enabled_servers}")
            
            # 检查MCP服务器详情
            print(f"   📊 服务器总数: {len(config.mcp.servers)}")
            for name, server in config.mcp.servers.items():
                if server.enabled:
                    print(f"   🟢 {name}: {server.type} - {server.description}")
                    if server.type == "sse":
                        print(f"      URL: {server.url}")
                    elif server.type == "stdio":
                        print(f"      命令: {server.command} {' '.join(server.args or [])}")
                else:
                    print(f"   🔴 {name}: 已禁用")
        except Exception as e:
            print(f"   ❌ 配置加载失败: {e}")
            return

        # 2. 检查编码设置
        print("\n2. 🔤 检查编码设置...")
        print(f"   系统编码: {sys.stdout.encoding}")
        print(f"   文件系统编码: {sys.getfilesystemencoding()}")
        print(f"   默认编码: {sys.getdefaultencoding()}")
        
        # 测试中文输出
        test_chinese = "🔧 当前可用的MCP工具"
        print(f"   中文测试: {test_chinese}")

        # 3. 创建TinyAgent实例
        print("\n3. 🤖 创建TinyAgent实例...")
        try:
            agent = TinyAgent()
            print(f"   ✅ TinyAgent创建成功")
            print(f"   智能模式: {agent.intelligent_mode}")
            print(f"   流式输出: {agent.use_streaming}")
        except Exception as e:
            print(f"   ❌ TinyAgent创建失败: {e}")
            traceback.print_exc()
            return

        # 4. 测试MCP连接
        print("\n4. 🔌 测试MCP服务器连接...")
        try:
            # 获取MCP连接状态
            connection_status = agent.get_mcp_connection_status()
            if connection_status:
                for server_name, status in connection_status.items():
                    print(f"   📡 {server_name}: {status}")
            else:
                print("   ⚠️ 没有连接状态信息")
            
            # 尝试建立连接
            print("   🔄 尝试建立MCP连接...")
            connected_servers = await agent._ensure_mcp_connections()
            print(f"   ✅ 成功连接 {len(connected_servers)} 个服务器")
            
            # 列出活跃服务器
            active_servers = agent.get_active_mcp_servers()
            print(f"   📊 活跃服务器: {active_servers}")
            
        except Exception as e:
            print(f"   ❌ MCP连接失败: {e}")
            traceback.print_exc()

        # 5. 测试工具发现
        print("\n5. 🛠️ 测试工具发现...")
        try:
            tools = await agent.get_available_tools_async()
            print(f"   ✅ 发现 {len(tools)} 个工具")
            for tool in tools[:5]:  # 只显示前5个
                print(f"   🔧 {tool}")
        except Exception as e:
            print(f"   ❌ 工具发现失败: {e}")
            traceback.print_exc()

        # 6. 测试my-search服务器连接
        print("\n6. 🔍 专门测试my-search服务器...")
        try:
            # 直接测试SSE连接
            from agents.mcp import MCPServerSse
            
            sse_config = {
                "url": "http://localhost:8081/sse",
                "headers": {},
                "timeout": 30.0,
                "sse_read_timeout": 120.0
            }
            
            print(f"   📡 尝试连接到: {sse_config['url']}")
            
            server = MCPServerSse(name="my-search-test", params=sse_config)
            
            # 尝试连接
            await asyncio.wait_for(server.connect(), timeout=10.0)
            print(f"   ✅ my-search连接成功!")
            
            # 尝试列出工具
            tools_response = await server.list_tools()
            if hasattr(tools_response, 'tools'):
                tools_list = tools_response.tools
            else:
                tools_list = tools_response
                
            print(f"   🛠️ 发现 {len(tools_list)} 个工具:")
            for tool in tools_list:
                print(f"      - {tool.name}: {tool.description}")
                
            # 🔧 FIX: 正确关闭连接
            try:
                if hasattr(server, '__aexit__'):
                    await server.__aexit__(None, None, None)
                elif hasattr(server, 'disconnect'):
                    await server.disconnect()
                print("   ✅ my-search连接已正确关闭")
            except Exception as close_error:
                print(f"   ⚠️ 关闭连接时的警告: {close_error}")
            
        except asyncio.TimeoutError:
            print(f"   ❌ my-search连接超时 (10秒)")
            print(f"   💡 请确认服务器在 http://localhost:8081 正在运行")
        except Exception as e:
            print(f"   ❌ my-search连接失败: {e}")
            print(f"   💡 错误类型: {type(e).__name__}")

        # 7. 测试智能查询处理
        print("\n7. 🧠 测试智能查询处理...")
        try:
            # 直接测试工具查询
            if agent._intelligent_agent:
                intelligent_agent = agent._get_intelligent_agent()
                if intelligent_agent._detect_tool_query("检查可用工具"):
                    print("   ✅ 工具查询检测成功")
                    response = await intelligent_agent._handle_tool_query()
                    print("   📄 工具查询响应长度:", len(response))
                    # 显示前500字符避免输出过长
                    print("   📄 响应预览:", response[:500] + ("..." if len(response) > 500 else ""))
                else:
                    print("   ❌ 工具查询检测失败")
            else:
                print("   ⚠️ 智能代理未初始化")
        except Exception as e:
            print(f"   ❌ 智能查询测试失败: {e}")
            traceback.print_exc()

    except Exception as e:
        print(f"\n❌ 调试过程中发生错误: {e}")
        traceback.print_exc()
    
    finally:
        # 8. 关闭连接
        print("\n8. 🔒 清理连接...")
        try:
            if agent:
                await agent.close_mcp_connections()
                print("   ✅ 连接清理完成")
        except Exception as e:
            print(f"   ⚠️ 连接清理警告: {e}")

        print("\n🎉 调试完成!")

if __name__ == "__main__":
    print("启动MCP问题调试器...")
    
    # 🔧 FIX: 更好的异步清理
    try:
        asyncio.run(debug_mcp_issues())
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断")
    except Exception as e:
        print(f"\n❌ 程序异常: {e}")
    finally:
        # 强制清理所有异步资源
        try:
            loop = asyncio.get_event_loop()
            if not loop.is_closed():
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
        except:
            pass 