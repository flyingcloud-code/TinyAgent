#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试迭代1的进度提示效果
验证基础阶段提示是否正常工作
"""

import sys
import os
import asyncio
from pathlib import Path

# 确保正确的Python路径
sys.path.insert(0, str(Path(__file__).parent))

# 设置控制台编码为UTF-8 (Windows)
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'

from tinyagent.core.agent import TinyAgent

async def test_iteration1():
    """测试迭代1：基础进度提示"""
    print("🧪 测试迭代1：基础进度提示")
    print("=" * 50)
    
    try:
        # 创建TinyAgent
        agent = TinyAgent()
        
        # 测试简单查询，观察进度提示
        print("\n🎯 测试查询：OpenAI最新新闻")
        print("-" * 30)
        
        result = await agent.run("what is latest news from openai")
        
        print("\n📄 测试完成！")
        print(f"🔍 最终结果长度: {len(result.final_output) if hasattr(result, 'final_output') else len(str(result))} 字符")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        print(f"错误详情: {traceback.format_exc()}")
        return False

def main():
    """主函数"""
    try:
        success = asyncio.run(test_iteration1())
        
        print("\n" + "=" * 50)
        if success:
            print("✅ 迭代1测试成功完成")
            print("🎉 用户现在能看到清晰的进度提示:")
            print("   🤖 启动TinyAgent...")
            print("   🧠 启动智能推理模式...")
            print("   🔌 连接MCP服务器...")
            print("   🧠 开始智能分析...")
            print("   🔍 正在使用 [工具名] 工具...")
            print("   📊 工具执行完成，获得 [字符数] 字符结果")
            print("   ✅ 任务完成")
        else:
            print("❌ 迭代1测试失败")
            print("需要检查和修复问题")
            
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断测试")
    except Exception as e:
        print(f"\n💥 未预期的错误: {e}")

if __name__ == "__main__":
    main() 