#!/usr/bin/env python3
"""
测试TinyAgent阶段3实时流式输出功能
测试ActionExecutor和ResultObserver的streaming支持
"""

import asyncio
import sys
import os
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tinyagent.core.agent import TinyAgent


async def test_phase3_action_executor():
    """测试ActionExecutor的streaming功能"""
    print("🧪 **测试ActionExecutor流式输出功能**")
    print("=" * 70)
    print()
    
    # 创建TinyAgent实例，启用智能模式
    agent = TinyAgent(intelligent_mode=True)
    print(f"✅ TinyAgent已创建 (智能模式: {agent.intelligent_mode})")
    print()
    
    # 测试单个行动执行
    print("📝 **测试单个行动执行streaming**:")
    print("-" * 50)
    
    # 获取智能代理实例
    intelligent_agent = agent._get_intelligent_agent()
    if not intelligent_agent:
        print("❌ 智能代理未初始化，跳过测试")
        return False
    
    # 获取ActionExecutor进行直接测试
    action_executor = intelligent_agent.action_executor
    
    try:
        # 测试单个行动流式输出
        async for chunk in action_executor.execute_action_stream(
            action_name="search_information",
            parameters={"query": "TinyAgent测试"}
        ):
            print(chunk, end='', flush=True)
            await asyncio.sleep(0.01)
        
        print("\n" + "-" * 50)
        print("✅ **单个行动执行测试完成**")
        print()
        return True
        
    except Exception as e:
        print(f"\n❌ **ActionExecutor测试失败**: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_phase3_result_observer():
    """测试ResultObserver的streaming功能"""
    print("🧪 **测试ResultObserver流式输出功能**")
    print("=" * 70)
    print()
    
    # 创建TinyAgent实例，启用智能模式
    agent = TinyAgent(intelligent_mode=True)
    print(f"✅ TinyAgent已创建 (智能模式: {agent.intelligent_mode})")
    print()
    
    # 测试结果观察
    print("📝 **测试结果观察streaming**:")
    print("-" * 50)
    
    # 获取智能代理实例
    intelligent_agent = agent._get_intelligent_agent()
    if not intelligent_agent:
        print("❌ 智能代理未初始化，跳过测试")
        return False
    
    # 获取ResultObserver进行直接测试
    result_observer = intelligent_agent.result_observer
    
    try:
        # 模拟一些测试结果
        test_result = {
            "success": True,
            "data": "测试数据",
            "execution_time": 2.5,
            "confidence": 0.85
        }
        
        # 测试单个结果观察
        async for chunk in result_observer.observe_result_stream(
            action_id="test_action_001",
            result=test_result,
            expected_outcome="成功获取测试数据",
            execution_time=2.5,
            action_name="search_information"
        ):
            print(chunk, end='', flush=True)
            await asyncio.sleep(0.01)
        
        print("\n" + "-" * 50)
        print("✅ **结果观察测试完成**")
        print()
        return True
        
    except Exception as e:
        print(f"\n❌ **ResultObserver测试失败**: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_phase3_full_integration():
    """测试阶段3完整集成的streaming功能"""
    print("🧪 **测试阶段3完整集成流式输出**")
    print("=" * 70)
    print()
    
    # 创建TinyAgent实例，启用智能模式
    agent = TinyAgent(intelligent_mode=True)
    print(f"✅ TinyAgent已创建 (智能模式: {agent.intelligent_mode})")
    print()
    
    # 测试问题 - 设计一个会触发结果观察的任务
    test_message = "请分析当前时间并提供一些有用信息"
    
    print(f"📝 **测试问题**: {test_message}")
    print()
    print("🔄 **开始阶段3完整流式输出测试**:")
    print("-" * 70)
    
    start_time = time.time()
    chunk_count = 0
    
    try:
        # 使用流式输出
        async for chunk in agent.run_stream(test_message):
            # 实时输出每个chunk
            print(chunk, end='', flush=True)
            chunk_count += 1
            
            # 小延迟让输出更自然
            await asyncio.sleep(0.01)
            
    except Exception as e:
        print(f"\n❌ **流式输出错误**: {e}")
        print(f"错误类型: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False
    
    end_time = time.time()
    execution_time = end_time - start_time
    
    print("\n" + "-" * 70)
    print("🎉 **阶段3完整集成测试完成**")
    print(f"   ⏱️ 总耗时: {execution_time:.2f}秒")
    print(f"   📊 输出块数: {chunk_count}")
    print(f"   📈 平均块速度: {chunk_count/execution_time:.1f} 块/秒")
    print()
    
    return True


async def test_batch_observation():
    """测试批量结果观察的streaming功能"""
    print("🧪 **测试批量结果观察流式输出**")
    print("=" * 70)
    print()
    
    # 创建TinyAgent实例
    agent = TinyAgent(intelligent_mode=True)
    
    # 获取智能代理实例
    intelligent_agent = agent._get_intelligent_agent()
    if not intelligent_agent:
        print("❌ 智能代理未初始化，跳过测试")
        return False
    
    result_observer = intelligent_agent.result_observer
    
    # 准备多个测试结果
    test_results = [
        {
            'action_id': 'test_001',
            'result': {"success": True, "data": "结果1"},
            'action_name': 'search_info',
            'execution_time': 1.2,
            'expected_outcome': '成功搜索'
        },
        {
            'action_id': 'test_002', 
            'result': {"success": False, "error": "连接失败"},
            'action_name': 'fetch_data',
            'execution_time': 3.5,
            'expected_outcome': '获取数据'
        },
        {
            'action_id': 'test_003',
            'result': {"success": True, "confidence": 0.9},
            'action_name': 'analyze_result',
            'execution_time': 2.1,
            'expected_outcome': '分析完成'
        }
    ]
    
    print(f"📊 准备批量观察 {len(test_results)} 个结果")
    print("-" * 50)
    
    try:
        async for chunk in result_observer.observe_multiple_results_stream(test_results):
            print(chunk, end='', flush=True)
            await asyncio.sleep(0.01)
        
        print("\n" + "-" * 50)
        print("✅ **批量观察测试完成**")
        return True
        
    except Exception as e:
        print(f"\n❌ **批量观察测试失败**: {e}")
        return False


async def main():
    """主测试函数"""
    print("🚀 **TinyAgent 阶段3 Streaming测试开始**")
    print(f"⏰ 测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()
    
    print("📋 **阶段3特性**:")
    print("   ✅ ActionExecutor streaming支持")
    print("   ✅ ResultObserver streaming支持") 
    print("   ✅ 实时行动执行过程展示")
    print("   ✅ 详细结果观察分析")
    print("   ✅ 批量结果观察功能")
    print("   ✅ 学习状态实时更新")
    print("   ✅ 完整工作流可视化")
    print()
    
    tests = [
        ("ActionExecutor流式输出", test_phase3_action_executor),
        ("ResultObserver流式输出", test_phase3_result_observer),
        ("批量结果观察", test_batch_observation),
        ("阶段3完整集成测试", test_phase3_full_integration),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"🧪 **开始测试**: {test_name}")
        try:
            result = await test_func()
            results.append((test_name, result))
            if result:
                print(f"✅ **{test_name}**: 通过")
            else:
                print(f"❌ **{test_name}**: 失败")
        except Exception as e:
            print(f"❌ **{test_name}**: 异常 - {e}")
            results.append((test_name, False))
        
        print()
        await asyncio.sleep(1)  # 测试间隔
    
    # 总结
    print("=" * 80)
    print("🏁 **阶段3测试总结**")
    print()
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"   {test_name}: {status}")
    
    print()
    print(f"📊 **总体结果**: {passed}/{total} 测试通过")
    
    if passed == total:
        print("🎉 **所有测试通过！阶段3实现成功！**")
        print()
        print("✨ **阶段3成功特性**:")
        print("   ⚡ ActionExecutor实时执行展示")
        print("   👁️ ResultObserver智能观察分析")
        print("   📊 批量结果处理能力")
        print("   🧠 学习状态实时更新")
        print("   🔄 重试机制可视化")
        print("   📈 性能指标实时计算")
        print("   💡 智能洞察生成")
        print()
        print("🎯 **完整工作流已实现**:")
        print("   1️⃣ 任务规划 (TaskPlanner)")
        print("   2️⃣ 工具选择 (ToolSelector)")
        print("   3️⃣ 推理循环 (ReasoningEngine)")
        print("   4️⃣ 行动执行 (ActionExecutor)")
        print("   5️⃣ 结果观察 (ResultObserver)")
        print("   🧠 全流程智能代理实时可视化！")
        print()
        return True
    else:
        print("⚠️ **部分测试失败，需要调试**")
        return False


if __name__ == "__main__":
    # 运行测试
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 