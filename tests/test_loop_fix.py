"""
测试工具注册循环问题修复
Test tool registration loop fix
"""

import asyncio
import sys
import os
import logging
import time
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tinyagent.core.agent import TinyAgent
from tinyagent.core.logging import log_technical, log_agent

# 设置日志级别为INFO以观察注册过程
logging.basicConfig(level=logging.INFO)

async def test_loop_fix():
    """测试工具注册循环问题修复"""
    print("=== 测试工具注册循环修复 ===")
    print(f"测试开始时间: {datetime.now()}")
    
    try:
        # 创建TinyAgent实例
        print("1. 创建TinyAgent实例...")
        agent = TinyAgent(intelligent_mode=True)
        
        # 获取智能代理
        print("2. 获取智能代理...")
        intelligent_agent = agent._get_intelligent_agent()
        
        if not intelligent_agent:
            print("❌ 智能代理未初始化")
            return False
        
        print("✅ 智能代理初始化成功")
        
        # 记录工具注册前的状态
        print("3. 检查初始状态...")
        initial_tool_count = len(getattr(intelligent_agent, '_mcp_tools', []))
        print(f"初始工具数量: {initial_tool_count}")
        
        # 第一次工具注册
        print("4. 第一次MCP工具注册...")
        start_time = time.time()
        await agent._register_mcp_tools_with_intelligent_agent(intelligent_agent)
        first_registration_time = time.time() - start_time
        
        first_tool_count = len(getattr(intelligent_agent, '_mcp_tools', []))
        print(f"第一次注册后工具数量: {first_tool_count}")
        print(f"第一次注册耗时: {first_registration_time:.2f}秒")
        
        # 第二次工具注册（应该检测到重复并跳过）
        print("5. 第二次MCP工具注册（测试重复检测）...")
        start_time = time.time()
        await agent._register_mcp_tools_with_intelligent_agent(intelligent_agent)
        second_registration_time = time.time() - start_time
        
        second_tool_count = len(getattr(intelligent_agent, '_mcp_tools', []))
        print(f"第二次注册后工具数量: {second_tool_count}")
        print(f"第二次注册耗时: {second_registration_time:.2f}秒")
        
        # 第三次工具注册（进一步验证）
        print("6. 第三次MCP工具注册（再次验证）...")
        start_time = time.time()
        await agent._register_mcp_tools_with_intelligent_agent(intelligent_agent)
        third_registration_time = time.time() - start_time
        
        third_tool_count = len(getattr(intelligent_agent, '_mcp_tools', []))
        print(f"第三次注册后工具数量: {third_tool_count}")
        print(f"第三次注册耗时: {third_registration_time:.2f}秒")
        
        # 验证结果
        print("\n=== 验证结果 ===")
        print(f"工具数量变化: {initial_tool_count} → {first_tool_count} → {second_tool_count} → {third_tool_count}")
        print(f"注册时间: {first_registration_time:.2f}s → {second_registration_time:.2f}s → {third_registration_time:.2f}s")
        
        # 检查工具列表中的重复
        all_tools = getattr(intelligent_agent, '_mcp_tools', [])
        tool_names = [tool.get('name') for tool in all_tools]
        unique_tool_names = list(set(tool_names))
        
        print(f"总工具数: {len(tool_names)}")
        print(f"唯一工具数: {len(unique_tool_names)}")
        
        # 判断测试结果
        success = True
        if len(tool_names) != len(unique_tool_names):
            print("❌ 发现重复工具！")
            duplicate_tools = [name for name in tool_names if tool_names.count(name) > 1]
            print(f"重复的工具: {list(set(duplicate_tools))}")
            success = False
        else:
            print("✅ 没有发现重复工具")
        
        # 检查第二次和第三次注册是否被正确跳过
        if second_tool_count != first_tool_count:
            print("❌ 第二次注册没有被正确跳过")
            success = False
        else:
            print("✅ 第二次注册被正确跳过")
        
        if third_tool_count != first_tool_count:
            print("❌ 第三次注册没有被正确跳过")
            success = False
        else:
            print("✅ 第三次注册被正确跳过")
        
        # 检查注册时间是否有明显减少（表明跳过了重复操作）
        if second_registration_time > first_registration_time * 0.5:
            print("⚠️  第二次注册时间没有明显减少，可能还有优化空间")
        else:
            print("✅ 第二次注册时间明显减少，重复检测生效")
        
        if success:
            print("\n🎉 工具注册循环问题修复测试通过！")
        else:
            print("\n❌ 工具注册循环问题仍然存在")
        
        return success
        
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        import traceback
        print(f"错误详情: {traceback.format_exc()}")
        return False
    
    finally:
        print(f"测试结束时间: {datetime.now()}")

async def main():
    """主函数"""
    success = await test_loop_fix()
    return 0 if success else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 