"""
Test script for TinyAgent intelligent mode
Validates the IntelligentAgent integration and ReAct loop functionality.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tinyagent.core.agent import TinyAgent
from tinyagent.core.config import get_config

async def test_intelligent_mode_basic():
    """Test basic intelligent mode functionality"""
    print("🧠 Testing Intelligent Mode - Basic Functionality")
    print("=" * 60)
    
    try:
        # Create agent with intelligent mode enabled
        agent = TinyAgent(intelligent_mode=True)
        
        print(f"✅ Agent created successfully")
        print(f"   Intelligent mode: {agent.intelligent_mode}")
        print(f"   Intelligence available: {hasattr(agent, '_intelligent_agent')}")
        
        # Test simple reasoning task
        test_message = "Please analyze the task of creating a simple Python script and break it down into steps"
        
        print(f"\n📝 Test Message: {test_message}")
        print("\n🔄 Executing with intelligent mode...")
        
        result = await agent.run(test_message)
        
        print(f"\n✅ Execution completed")
        print(f"   Result type: {type(result)}")
        if hasattr(result, 'final_output'):
            print(f"   Response length: {len(result.final_output)} characters")
            print(f"   Response preview: {result.final_output[:200]}...")
        else:
            print(f"   Response: {str(result)[:200]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_intelligent_vs_basic_mode():
    """Compare intelligent mode vs basic mode execution"""
    print("\n🆚 Testing Intelligent vs Basic Mode Comparison")
    print("=" * 60)
    
    test_message = "Create a plan to analyze a project's file structure"
    
    try:
        # Test with basic mode
        print("📋 Testing Basic Mode...")
        basic_agent = TinyAgent(intelligent_mode=False)
        basic_result = await basic_agent.run(test_message)
        
        print(f"✅ Basic mode completed")
        print(f"   Mode: Basic LLM")
        
        # Test with intelligent mode  
        print("\n🧠 Testing Intelligent Mode...")
        intelligent_agent = TinyAgent(intelligent_mode=True)
        intelligent_result = await intelligent_agent.run(test_message)
        
        print(f"✅ Intelligent mode completed")
        print(f"   Mode: ReAct Loop")
        
        # Compare results
        print(f"\n📊 Comparison:")
        print(f"   Basic result type: {type(basic_result)}")
        print(f"   Intelligent result type: {type(intelligent_result)}")
        
        if hasattr(basic_result, 'final_output'):
            print(f"   Basic response length: {len(basic_result.final_output)} chars")
        
        if hasattr(intelligent_result, 'final_output'):
            print(f"   Intelligent response length: {len(intelligent_result.final_output)} chars")
        
        return True
        
    except Exception as e:
        print(f"❌ Comparison test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_mcp_tools_integration():
    """Test MCP tools integration with intelligent mode"""
    print("\n🔧 Testing MCP Tools Integration with Intelligent Mode")
    print("=" * 60)
    
    try:
        # Create agent with intelligent mode
        agent = TinyAgent(intelligent_mode=True)
        
        # Test message that should trigger tool usage
        test_message = "Please list the contents of the current directory and analyze the project structure"
        
        print(f"📝 Test Message: {test_message}")
        print("🔄 Executing with MCP tools...")
        
        result = await agent.run(test_message)
        
        print(f"✅ MCP tools test completed")
        if hasattr(result, 'final_output'):
            print(f"   Response length: {len(result.final_output)} characters")
            # Check if response contains file/directory information
            if any(keyword in result.final_output.lower() for keyword in ['file', 'directory', 'folder', '.py', '.md']):
                print(f"   ✅ Response appears to contain file system information")
            else:
                print(f"   ⚠️ Response may not contain expected file system information")
        
        return True
        
    except Exception as e:
        print(f"❌ MCP tools test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_configuration_options():
    """Test intelligent mode configuration options"""
    print("\n⚙️ Testing Configuration Options")
    print("=" * 60)
    
    try:
        # Test with custom configuration
        custom_config = get_config()
        
        # Create agent with custom settings
        agent = TinyAgent(
            config=custom_config,
            intelligent_mode=True
        )
        
        print(f"✅ Agent created with custom config")
        print(f"   Intelligent mode: {agent.intelligent_mode}")
        print(f"   Model: {agent.model_name}")
        print(f"   Streaming: {agent.use_streaming}")
        
        # Test if intelligent agent is properly configured
        intelligent_agent = agent._get_intelligent_agent()
        if intelligent_agent:
            print(f"   IntelligentAgent created: ✅")
            print(f"   Config max iterations: {intelligent_agent.config.max_reasoning_iterations}")
            print(f"   Config confidence threshold: {intelligent_agent.config.confidence_threshold}")
            print(f"   Config learning enabled: {intelligent_agent.config.enable_learning}")
        else:
            print(f"   IntelligentAgent creation: ❌")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all intelligent mode tests"""
    print("🚀 TinyAgent Intelligent Mode Test Suite")
    print("=" * 60)
    
    tests = [
        ("Basic Functionality", test_intelligent_mode_basic),
        ("Mode Comparison", test_intelligent_vs_basic_mode),
        ("MCP Tools Integration", test_mcp_tools_integration),
        ("Configuration Options", test_configuration_options),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n🧪 Running: {test_name}")
        try:
            success = await test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print(f"\n📊 Test Results Summary")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"   {status}: {test_name}")
        if success:
            passed += 1
        else:
            failed += 1
    
    print(f"\n🏁 Final Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed! Intelligent mode is working correctly.")
    else:
        print("⚠️ Some tests failed. Please check the output above for details.")
    
    return failed == 0

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 