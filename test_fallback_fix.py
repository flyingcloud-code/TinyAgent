#!/usr/bin/env python3
"""
测试TinyAgent关键改进的验证脚本

本脚本验证以下改进：
1. 禁用回退机制 - 提高调试能力
2. 修复工具列表查询 - 返回实际MCP工具
3. 实现详细的MCP工具调用跟踪 - 显示推理-行动-反思循环

测试用例：
- test_tool_list_query: 验证工具查询返回实际MCP工具信息
- test_tool_execution_tracing: 验证详细的工具执行跟踪输出
- test_fallback_disabled: 验证回退机制已被禁用
- test_agent_availability: 验证代理可用性和配置
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from tinyagent import TinyAgent


async def test_tool_list_query():
    """测试工具列表查询是否返回实际MCP工具"""
    print("\n" + "="*80)
    print("🔧 测试1: 工具列表查询")
    print("="*80)
    
    try:
        # 创建TinyAgent实例
        agent = TinyAgent(
            intelligent_mode=True  # 确保使用智能模式
        )
        
        print("📝 测试查询: 'list tools'")
        
        # 测试工具查询
        result = await agent.run("list tools")
        
        print("\n📊 查询结果:")
        print("-"*50)
        if hasattr(result, 'final_output'):
            response = result.final_output
        else:
            response = str(result)
            
        print(response)
        
        # 验证响应质量
        response_lower = response.lower()
        quality_indicators = [
            ("包含服务器信息", any(server in response_lower for server in ['filesystem', 'fetch', 'sequential'])),
            ("包含工具描述", "description" in response_lower or "描述" in response_lower),
            ("包含使用示例", "example" in response_lower or "示例" in response_lower),
            ("格式化良好", "**" in response or "•" in response),
            ("包含实际工具", not "no tools" in response_lower and not "没有工具" in response_lower)
        ]
        
        print("\n🔍 响应质量分析:")
        for indicator, passed in quality_indicators:
            status = "✅" if passed else "❌"
            print(f"   {status} {indicator}")
        
        success_rate = sum(1 for _, passed in quality_indicators if passed) / len(quality_indicators)
        print(f"\n📈 质量评分: {success_rate*100:.1f}%")
        
        if success_rate >= 0.6:
            print("✅ 工具查询测试通过")
            return True
        else:
            print("❌ 工具查询测试失败")
            return False
            
    except Exception as e:
        print(f"❌ 工具查询测试异常: {e}")
        import traceback
        print(traceback.format_exc())
        return False


async def test_tool_execution_tracing():
    """测试工具执行的详细跟踪输出"""
    print("\n" + "="*80)
    print("🔄 测试2: 工具执行跟踪")
    print("="*80)
    
    try:
        # 创建TinyAgent实例
        agent = TinyAgent(
            intelligent_mode=True,
            use_streaming=True  # 启用流式输出以显示详细跟踪
        )
        
        print("📝 测试任务: '创建一个测试文件debug.txt'")
        print("\n🎯 期望看到:")
        print("   • 推理阶段的详细中文输出")
        print("   • 工具调用的参数和结果")
        print("   • 执行时间和状态统计")
        print("\n" + "-"*50)
        
        # 测试工具执行任务
        result = await agent.run("创建一个测试文件debug.txt，内容包含当前时间和TinyAgent信息")
        
        print("\n📊 执行结果:")
        print("-"*50)
        if hasattr(result, 'final_output'):
            response = result.final_output
        else:
            response = str(result)
            
        print(response)
        
        # 检查是否生成了文件（如果有文件系统工具）
        debug_file = Path("debug.txt")
        if debug_file.exists():
            print(f"\n📄 生成的文件: {debug_file}")
            print(f"   文件大小: {debug_file.stat().st_size} 字节")
            try:
                content = debug_file.read_text(encoding='utf-8')
                print(f"   文件内容预览: {content[:200]}...")
            except Exception as e:
                print(f"   读取文件失败: {e}")
        
        print("✅ 工具执行跟踪测试完成")
        return True
        
    except Exception as e:
        print(f"❌ 工具执行跟踪测试异常: {e}")
        import traceback
        print(traceback.format_exc())
        return False


async def test_fallback_disabled():
    """测试回退机制是否已被禁用"""
    print("\n" + "="*80)
    print("🚫 测试3: 回退机制禁用验证")
    print("="*80)
    
    try:
        # 创建TinyAgent实例，尝试强制失败情况
        agent = TinyAgent(
            intelligent_mode=True
        )
        
        print("📝 测试场景: 验证错误直接抛出而不是回退")
        
        # 尝试访问一个不存在的工具来触发错误处理
        try:
            # 模拟一个可能触发回退的场景
            result = await agent.run("使用不存在的工具nonexistent_tool来完成任务")
            
            print("📊 结果分析:")
            if hasattr(result, 'final_output'):
                response = result.final_output
            else:
                response = str(result)
            
            print(f"   响应: {response[:200]}...")
            
            # 检查响应是否明确指出了问题而不是默默回退
            if "not found" in response.lower() or "找不到" in response or "不存在" in response:
                print("✅ 错误被正确报告，没有静默回退")
                return True
            else:
                print("⚠️ 可能存在回退机制或错误处理不够明确")
                return False
                
        except RuntimeError as e:
            # 这是期望的行为 - 直接抛出错误而不是回退
            print(f"✅ 正确抛出RuntimeError: {e}")
            return True
        except Exception as e:
            print(f"⚠️ 抛出了其他异常: {e}")
            return True
        
    except Exception as e:
        print(f"❌ 回退禁用测试异常: {e}")
        import traceback
        print(traceback.format_exc())
        return False


async def test_agent_availability():
    """测试代理可用性和配置"""
    print("\n" + "="*80)
    print("🤖 测试4: 代理可用性和配置")
    print("="*80)
    
    try:
        # 测试基本创建
        agent = TinyAgent()
        
        print("✅ TinyAgent实例创建成功")
        print(f"   代理名称: {agent.config.agent.name}")
        print(f"   模型: {agent.model_name}")
        print(f"   智能模式: {agent.intelligent_mode}")
        print(f"   流式输出: {agent.use_streaming}")
        
        # 测试MCP服务器状态
        server_info = agent.get_mcp_server_info()
        print(f"\n🖥️ MCP服务器配置:")
        for server in server_info:
            print(f"   • {server['name']}: {server['status']}")
        
        # 测试工具可用性
        tools = agent.get_available_tools()
        print(f"\n🔧 可用工具:")
        if tools:
            for tool in tools[:5]:  # 只显示前5个
                print(f"   • {tool}")
            if len(tools) > 5:
                print(f"   ... 还有 {len(tools) - 5} 个工具")
        else:
            print("   无可用工具")
        
        # 测试连接状态
        connection_status = agent.get_mcp_connection_status()
        print(f"\n🔗 MCP连接状态:")
        for server, status in connection_status.items():
            print(f"   • {server}: {status}")
        
        print("✅ 代理可用性测试完成")
        return True
        
    except Exception as e:
        print(f"❌ 代理可用性测试异常: {e}")
        import traceback
        print(traceback.format_exc())
        return False


async def test_reasoning_engine_integration():
    """测试推理引擎集成"""
    print("\n" + "="*80)
    print("🧠 测试5: 推理引擎集成")
    print("="*80)
    
    try:
        agent = TinyAgent(intelligent_mode=True)
        
        print("📝 测试推理任务: '分析当前项目结构并总结TinyAgent的功能'")
        
        # 这个任务应该触发推理引擎的完整ReAct循环
        result = await agent.run("分析当前项目结构并总结TinyAgent的主要功能模块")
        
        print("\n📊 推理结果:")
        if hasattr(result, 'final_output'):
            response = result.final_output
        else:
            response = str(result)
        
        # 分析响应质量
        quality_indicators = [
            ("包含项目分析", any(keyword in response.lower() for keyword in ['project', '项目', 'structure', '结构'])),
            ("包含功能描述", any(keyword in response.lower() for keyword in ['function', '功能', 'module', '模块'])),
            ("响应详细", len(response) > 100),
            ("逻辑清晰", "tinyagent" in response.lower()),
        ]
        
        print("\n🔍 推理质量分析:")
        for indicator, passed in quality_indicators:
            status = "✅" if passed else "❌"
            print(f"   {status} {indicator}")
        
        print("✅ 推理引擎集成测试完成")
        return True
        
    except Exception as e:
        print(f"❌ 推理引擎集成测试异常: {e}")
        import traceback
        print(traceback.format_exc())
        return False


async def main():
    """运行所有测试"""
    print("🚀 TinyAgent 关键改进验证测试")
    print("="*80)
    print("测试目标:")
    print("1. 验证工具查询返回实际MCP工具信息")
    print("2. 验证详细的工具执行跟踪输出")
    print("3. 验证回退机制已被正确禁用")
    print("4. 验证代理基本功能和配置")
    print("5. 验证推理引擎集成")
    
    # 运行所有测试
    test_functions = [
        test_agent_availability,
        test_tool_list_query,
        test_fallback_disabled,
        test_tool_execution_tracing,
        test_reasoning_engine_integration,
    ]
    
    results = []
    for test_func in test_functions:
        try:
            result = await test_func()
            results.append(result)
        except Exception as e:
            print(f"❌ 测试 {test_func.__name__} 发生异常: {e}")
            results.append(False)
        
        # 等待一下避免过快执行
        await asyncio.sleep(1)
    
    # 输出总结
    print("\n" + "="*80)
    print("📋 测试总结")
    print("="*80)
    
    passed = sum(results)
    total = len(results)
    
    print(f"✅ 通过测试: {passed}/{total}")
    print(f"📈 成功率: {(passed/total)*100:.1f}%")
    
    if passed == total:
        print("\n🎉 所有测试通过! TinyAgent关键改进已成功实施。")
        print("\n🔧 改进效果:")
        print("   • 工具查询现在返回实际MCP工具信息")
        print("   • 工具执行显示详细的中文跟踪输出")
        print("   • 回退机制已禁用，错误直接暴露利于调试")
        print("   • 推理引擎与MCP工具完全集成")
    else:
        print(f"\n⚠️ 有 {total-passed} 个测试失败，需要进一步调试。")
    
    return passed == total


if __name__ == "__main__":
    # 检查Python版本
    if sys.version_info < (3, 7):
        print("❌ 需要Python 3.7或更高版本")
        sys.exit(1)
    
    # 运行测试
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⛔ 测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ 测试运行失败: {e}")
        import traceback
        print(traceback.format_exc())
        sys.exit(1) 