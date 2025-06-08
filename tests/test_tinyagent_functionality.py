#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TinyAgent功能测试脚本
验证核心功能是否正常工作
"""

import sys
import os
import asyncio
from pathlib import Path

# 确保正确的Python路径
sys.path.insert(0, str(Path(__file__).parent))

# 设置控制台编码为UTF-8
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'

from tinyagent.core.agent import TinyAgent

async def test_basic_functionality():
    """测试TinyAgent基本功能"""
    print("🧪 TinyAgent功能测试")
    print("=" * 50)
    
    agent = None
    
    try:
        # 1. 创建代理
        print("\n1. 🤖 创建TinyAgent...")
        agent = TinyAgent()
        print("   ✅ TinyAgent创建成功")
        
        # 2. 测试工具查询
        print("\n2. 🔧 测试工具查询...")
        try:
            result = await agent.run("list tools")
            print("   ✅ 工具查询成功")
            if hasattr(result, 'final_output'):
                result_text = result.final_output
            else:
                result_text = str(result)
            print(f"   📄 响应长度: {len(result_text)} 字符")
            # 显示前300字符
            print(f"   📄 响应预览: {result_text[:300]}...")
        except Exception as e:
            print(f"   ❌ 工具查询失败: {e}")
        
        # 3. 测试文件操作
        print("\n3. 📁 测试文件操作...")
        try:
            # 读取README文件
            result = await agent.run("读取README.md文件的前100行内容")
            print("   ✅ 文件读取成功")
            if hasattr(result, 'final_output'):
                result_text = result.final_output
            else:
                result_text = str(result)
            print(f"   📄 响应长度: {len(result_text)} 字符")
            # 显示前200字符
            print(f"   📄 响应预览: {result_text[:200]}...")
        except Exception as e:
            print(f"   ❌ 文件读取失败: {e}")
        
        # 4. 测试中文处理
        print("\n4. 🔤 测试中文处理...")
        try:
            result = await agent.run("你好，请告诉我当前项目的主要功能是什么？")
            print("   ✅ 中文处理成功")
            if hasattr(result, 'final_output'):
                result_text = result.final_output
            else:
                result_text = str(result)
            print(f"   📄 响应长度: {len(result_text)} 字符")
            # 显示前200字符
            print(f"   📄 响应预览: {result_text[:200]}...")
        except Exception as e:
            print(f"   ❌ 中文处理失败: {e}")
        
        # 5. 测试搜索功能（如果my-search可用）
        print("\n5. 🔍 测试搜索功能...")
        try:
            result = await agent.run("搜索今天的天气信息")
            print("   ✅ 搜索功能成功")
            if hasattr(result, 'final_output'):
                result_text = result.final_output
            else:
                result_text = str(result)
            print(f"   📄 响应长度: {len(result_text)} 字符")
            # 显示前200字符
            print(f"   📄 响应预览: {result_text[:200]}...")
        except Exception as e:
            print(f"   ❌ 搜索功能失败: {e}")
        
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 清理连接
        if agent:
            try:
                await agent.close_mcp_connections()
                print("\n🔒 连接清理完成")
            except Exception as e:
                print(f"\n⚠️ 连接清理警告: {e}")
    
    print("\n🎉 功能测试完成!")

def test_sync_functionality():
    """测试同步功能"""
    print("\n🔄 测试同步接口...")
    
    try:
        agent = TinyAgent()
        
        # 测试同步工具查询
        result = agent.run_sync("list available tools")
        print("   ✅ 同步工具查询成功")
        if hasattr(result, 'final_output'):
            result_text = result.final_output
        else:
            result_text = str(result)
        print(f"   📄 响应长度: {len(result_text)} 字符")
        print(f"   📄 响应预览: {result_text[:200]}...")
        
    except Exception as e:
        print(f"   ❌ 同步功能失败: {e}")

if __name__ == "__main__":
    print("启动TinyAgent功能测试...")
    
    # 异步测试
    asyncio.run(test_basic_functionality())
    
    # 同步测试
    test_sync_functionality()
    
    print("\n✨ 所有测试完成!") 