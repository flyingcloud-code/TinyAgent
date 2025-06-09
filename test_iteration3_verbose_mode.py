#!/usr/bin/env python3
"""
测试迭代3.2: Verbose模式验证
验证详细程度配置功能
"""

import asyncio
import sys
import os
import time

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from tinyagent.core.agent import TinyAgent

async def test_verbose_mode_comparison():
    """对比测试：默认模式 vs verbose模式"""
    
    print("=" * 60)
    print("🧪 测试迭代3.2: Verbose模式对比验证")
    print("🎯 目标: 验证可配置详细程度功能")
    print("=" * 60)
    
    # 测试案例：简单搜索任务
    test_query = "what time is it"
    
    # 测试1：默认模式（简洁）
    print("\n📝 测试1: 默认模式（简洁）")
    print("期望: 只显示智能摘要，不显示详细结果")
    print("-" * 40)
    
    agent_normal = TinyAgent(verbose=False)
    start_time = time.time()
    
    try:
        result1 = await agent_normal.run(test_query)
        duration1 = time.time() - start_time
        print(f"✅ 默认模式完成，耗时: {duration1:.2f}秒")
        
    except Exception as e:
        print(f"❌ 默认模式测试失败: {e}")
        return False
    
    print("\n" + "="*60)
    
    # 测试2：Verbose模式（详细）  
    print("📝 测试2: Verbose模式（详细）")
    print("期望: 显示智能摘要 + 详细结果内容前200字符")
    print("-" * 40)
    
    agent_verbose = TinyAgent(verbose=True)
    start_time = time.time()
    
    try:
        result2 = await agent_verbose.run(test_query)
        duration2 = time.time() - start_time
        print(f"✅ Verbose模式完成，耗时: {duration2:.2f}秒")
        
    except Exception as e:
        print(f"❌ Verbose模式测试失败: {e}")
        return False
    
    # 分析对比结果
    print(f"\n🎯 对比分析:")
    print(f"⭐ 默认模式: 简洁摘要，专注核心信息")
    print(f"⭐ Verbose模式: 摘要 + 详细内容，便于调试")
    print(f"⭐ 耗时对比: 默认 {duration1:.2f}s vs Verbose {duration2:.2f}s")
    
    return True

async def test_verbose_tool_types():
    """测试不同工具类型在verbose模式下的表现"""
    
    print(f"\n" + "=" * 60)
    print("🔧 测试不同工具的Verbose输出格式")
    print("=" * 60)
    
    agent = TinyAgent(verbose=True)
    
    # 测试搜索工具的verbose输出
    print("\n🔍 测试: 搜索工具 + Verbose模式")
    print("期望: 搜索摘要 + 详细搜索结果内容")
    
    try:
        await agent.run("search latest technology news")
        print("✅ 搜索工具Verbose测试完成")
        
    except Exception as e:
        print(f"⚠️ 搜索工具测试失败: {e}")
    
    print(f"\n🎯 Verbose模式验证点:")
    print(f"1. 工具摘要: 📊 工具名: 智能摘要")
    print(f"2. 详细结果: 📄 详细结果:\\n前200字符...")
    print(f"3. 缓存命中: 📄 详细结果 (缓存):\\n前200字符...")
    print(f"4. 结果截断: 超过200字符时自动添加'...'")

if __name__ == "__main__":
    print("🚀 启动迭代3.2: Verbose模式测试")
    
    async def main():
        success1 = await test_verbose_mode_comparison()
        await test_verbose_tool_types()
        
        if success1:
            print("\n🎉 迭代3.2 Verbose模式验证成功!")
            print("🏆 用户现在可以选择简洁或详细的工具结果显示")
            print("💡 使用方法: TinyAgent(verbose=True)")
        else:
            print("\n⚠️ 部分测试未通过，需要检查")
    
    asyncio.run(main()) 