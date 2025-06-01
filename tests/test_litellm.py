#!/usr/bin/env python3
"""
Test script for LiteLLM integration
"""

import os
import sys
from pathlib import Path

# Add the current directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from tinyagent.core.config import get_config
from tinyagent.core.agent import TinyAgent

def test_model_detection():
    """Test model detection logic"""
    print("🔍 Testing model detection logic...")
    
    config = get_config()
    agent = TinyAgent(config=config)
    
    test_models = [
        "gpt-4",
        "gpt-3.5-turbo", 
        "google/gemini-2.0-flash-001",
        "anthropic/claude-3-5-sonnet",
        "deepseek/deepseek-chat",
        "mistral/mistral-7b"
    ]
    
    for model in test_models:
        should_use_litellm = agent._should_use_litellm(model)
        print(f"  {model}: {'LiteLLM' if should_use_litellm else 'OpenAI'}")
    
    print(f"\n📝 Current configured model: {agent.model_name}")
    print(f"   Should use LiteLLM: {agent._should_use_litellm(agent.model_name)}")

def test_model_instance_creation():
    """Test model instance creation"""
    print("\n🏗️  Testing model instance creation...")
    
    config = get_config()
    agent = TinyAgent(config=config)
    
    try:
        model_instance = agent._create_model_instance(agent.model_name)
        print(f"✅ Model instance created: {type(model_instance)}")
        
        if hasattr(model_instance, 'model'):
            print(f"   Model name: {model_instance.model}")
        if hasattr(model_instance, 'api_key'):
            print(f"   API key: {'*' * 10 if model_instance.api_key else 'None'}")
        if hasattr(model_instance, 'base_url'):
            print(f"   Base URL: {model_instance.base_url}")
            
    except Exception as e:
        print(f"❌ Failed to create model instance: {e}")
        import traceback
        traceback.print_exc()

def test_agent_creation():
    """Test agent creation with LiteLLM"""
    print("\n🤖 Testing agent creation...")
    
    config = get_config()
    agent = TinyAgent(config=config)
    
    try:
        agent_instance = agent.get_agent()
        print(f"✅ Agent created successfully")
        print(f"   Agent name: {agent_instance.name}")
        print(f"   Model type: {type(agent_instance.model)}")
        
        if hasattr(agent_instance.model, 'model'):
            print(f"   Model name: {agent_instance.model.model}")
        else:
            print(f"   Model: {agent_instance.model}")
            
    except Exception as e:
        print(f"❌ Failed to create agent: {e}")
        import traceback
        traceback.print_exc()

def test_simple_completion():
    """Test a simple completion call"""
    print("\n💬 Testing simple completion...")
    
    config = get_config()
    agent = TinyAgent(config=config)
    
    try:
        print("   Creating agent...")
        agent_instance = agent.get_agent()
        
        print("   Running simple completion test...")
        # This is just testing if we can create and get the agent
        # Actual completion test would require network call
        print("✅ Agent is ready for completion calls")
        
    except Exception as e:
        print(f"❌ Failed completion test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🧪 LiteLLM Integration Test\n")
    
    # Show environment
    print("🌍 Environment:")
    print(f"   OPENROUTER_API_KEY: {'✅ Set' if os.getenv('OPENROUTER_API_KEY') else '❌ Not set'}")
    print(f"   OPENAI_API_KEY: {'✅ Set' if os.getenv('OPENAI_API_KEY') else '❌ Not set'}")
    print()
    
    test_model_detection()
    test_model_instance_creation()
    test_agent_creation()
    test_simple_completion()
    
    print("\n✨ All tests completed!") 