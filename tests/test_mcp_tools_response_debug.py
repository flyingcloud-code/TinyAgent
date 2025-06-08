#!/usr/bin/env python3
"""
调试MCP服务器工具响应格式
"""

import asyncio
import logging
from tinyagent.core.agent import create_agent
from tinyagent.core.logging import setup_logging, log_technical
from tinyagent.core.config import get_config

async def debug_mcp_tool_response():
    """调试MCP服务器的工具响应格式"""
    
    # 设置日志
    config = get_config()
    logger = setup_logging(config.logging)
    
    print("🔍 调试MCP服务器工具响应格式")
    print("="*60)
    
    # 创建代理
    agent = create_agent()
    
    # 建立MCP连接
    print("🔗 建立MCP连接...")
    connected_servers = await agent._ensure_mcp_connections()
    print(f"✅ 连接了 {len(connected_servers)} 个服务器")
    
    # 检查每个连接的工具响应格式
    for server_name, connection in agent._persistent_connections.items():
        print(f"\n📡 检查服务器: {server_name}")
        print("-" * 40)
        
        try:
            if hasattr(connection, 'list_tools'):
                print(f"✅ 服务器支持 list_tools")
                
                # 获取工具响应
                server_tools = await connection.list_tools()
                
                print(f"🔍 响应类型: {type(server_tools)}")
                print(f"🔍 响应属性: {dir(server_tools)}")
                
                # 检查是否有tools属性
                if hasattr(server_tools, 'tools'):
                    tools = server_tools.tools
                    print(f"✅ 有 .tools 属性，类型: {type(tools)}")
                    print(f"🔧 工具数量: {len(tools)}")
                    
                    # 检查第一个工具的格式
                    if tools:
                        first_tool = tools[0]
                        print(f"🔍 第一个工具类型: {type(first_tool)}")
                        print(f"🔍 第一个工具属性: {dir(first_tool)}")
                        
                        # 检查工具的关键属性
                        if hasattr(first_tool, 'name'):
                            print(f"✅ 工具名称: {first_tool.name}")
                        if hasattr(first_tool, 'description'):
                            print(f"✅ 工具描述: {getattr(first_tool, 'description', 'N/A')}")
                        if hasattr(first_tool, 'inputSchema'):
                            print(f"✅ 输入schema: 存在")
                        else:
                            print(f"⚠️  没有 inputSchema 属性")
                else:
                    print(f"❌ 没有 .tools 属性")
                    print(f"🔍 可用属性: {[attr for attr in dir(server_tools) if not attr.startswith('_')]}")
                    
                    # 尝试其他可能的属性名
                    for attr_name in ['tools', 'tool_list', 'available_tools', 'items']:
                        if hasattr(server_tools, attr_name):
                            attr_value = getattr(server_tools, attr_name)
                            print(f"🔍 找到属性 {attr_name}: {type(attr_value)}")
                            if hasattr(attr_value, '__len__'):
                                print(f"   长度: {len(attr_value)}")
                            if hasattr(attr_value, '__iter__') and len(attr_value) > 0:
                                print(f"   第一个元素: {type(attr_value[0])}")
            else:
                print(f"❌ 服务器不支持 list_tools")
                
        except Exception as e:
            print(f"❌ 检查服务器 {server_name} 失败: {e}")
            import traceback
            print(f"详细错误: {traceback.format_exc()}")
    
    print("\n" + "="*60)
    print("🏁 调试完成")

# 主程序
if __name__ == "__main__":
    asyncio.run(debug_mcp_tool_response()) 