OpenAI Agents Python in contxt7 site

## link
https://context7.com/openai/openai-agents-python/llms.txt

## full content listed below as well for fast access
TITLE: Creating a Single Agent (Python)
DESCRIPTION: This snippet demonstrates how to instantiate a basic `Agent` object from the `agents` library. An agent is defined by its `name` and `instructions`, which guide its behavior and responses.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/docs/quickstart.md#_snippet_4

LANGUAGE: python
CODE:
```
from agents import Agent

agent = Agent(
    name="Math Tutor",
    instructions="You provide help with math problems. Explain your reasoning at each step and include examples",
)
```

----------------------------------------

TITLE: Configuring a Basic Agent with Tools (Python)
DESCRIPTION: This snippet demonstrates the basic configuration of an `Agent` in Python, including setting its name, instructions, the LLM model to use, and integrating a custom `function_tool`. The `get_weather` function is decorated as a tool, allowing the agent to use it for specific tasks.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/docs/agents.md#_snippet_0

LANGUAGE: python
CODE:
```
from agents import Agent, ModelSettings, function_tool

@function_tool
def get_weather(city: str) -> str:
    return f"The weather in {city} is sunny"

agent = Agent(
    name="Haiku agent",
    instructions="Always respond in haiku form",
    model="o3-mini",
    tools=[get_weather],
)
```

----------------------------------------

TITLE: Running an Agent Asynchronously with Runner.run() in Python
DESCRIPTION: This snippet demonstrates how to initialize an `Agent` and execute it asynchronously using `Runner.run()`. It shows how to pass an initial prompt to the agent and print its final output. The `Runner.run()` method returns a `RunResult` object containing the execution outcome.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/docs/running_agents.md#_snippet_0

LANGUAGE: Python
CODE:
```
from agents import Agent, Runner

async def main():
    agent = Agent(name="Assistant", instructions="You are a helpful assistant")

    result = await Runner.run(agent, "Write a haiku about recursion in programming.")
    print(result.final_output)
    # Code within the code,
    # Functions calling themselves,
    # Infinite loop's dance.
```

----------------------------------------

TITLE: Activating Virtual Environment (Bash)
DESCRIPTION: This command activates the previously created Python virtual environment. It must be run in every new terminal session to ensure that subsequent Python commands and package installations are isolated within this environment.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/docs/quickstart.md#_snippet_1

LANGUAGE: bash
CODE:
```
source .venv/bin/activate
```

----------------------------------------

TITLE: Setting Up Python Virtual Environment
DESCRIPTION: This snippet demonstrates how to create and activate a Python virtual environment, which is a best practice for managing project dependencies and avoiding conflicts.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/README.md#_snippet_0

LANGUAGE: bash
CODE:
```
python -m venv env
source env/bin/activate
```

----------------------------------------

TITLE: Basic Agent Creation and Execution (Hello World)
DESCRIPTION: This example shows how to create a simple `Agent` with instructions and use `Runner.run_sync` to execute a task. It demonstrates a basic synchronous interaction with the agent to generate a haiku.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/README.md#_snippet_2

LANGUAGE: python
CODE:
```
from agents import Agent, Runner

agent = Agent(name="Assistant", instructions="You are a helpful assistant")

result = Runner.run_sync(agent, "Write a haiku about recursion in programming.")
print(result.final_output)

# Code within the code,
# Functions calling themselves,
# Infinite loop's dance.
```

----------------------------------------

TITLE: Installing OpenAI Agents SDK
DESCRIPTION: This command installs the OpenAI Agents SDK using pip. An optional 'voice' group can be installed for voice support by appending '[voice]' to the package name.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/README.md#_snippet_1

LANGUAGE: bash
CODE:
```
pip install openai-agents
```

----------------------------------------

TITLE: Initializing Agent with Web and File Search Tools and Running a Query (Python)
DESCRIPTION: This Python snippet demonstrates how to initialize an `Agent` with `WebSearchTool` and `FileSearchTool`. The `FileSearchTool` is configured to return a maximum of 3 results and uses a specified vector store ID. The `main` asynchronous function then shows how to execute a query using `Runner.run` with the configured agent and print the final output from the agent's response.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/docs/tools.md#_snippet_0

LANGUAGE: Python
CODE:
```
from agents import Agent, FileSearchTool, Runner, WebSearchTool

agent = Agent(
    name="Assistant",
    tools=[
        WebSearchTool(),
        FileSearchTool(
            max_num_results=3,
            vector_store_ids=["VECTOR_STORE_ID"],
        ),
    ],
)

async def main():
    result = await Runner.run(agent, "Which coffee shop should I go to, taking into account my preferences and the weather today in SF?")
    print(result.final_output)
```

----------------------------------------

TITLE: Setting OpenAI API Key Environment Variable (Bash)
DESCRIPTION: This snippet shows how to set the `OPENAI_API_KEY` environment variable in a bash shell. This key is crucial for the OpenAI Agents SDK to authenticate and interact with the OpenAI API services.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/docs/index.md#_snippet_2

LANGUAGE: bash
CODE:
```
export OPENAI_API_KEY=sk-...
```

----------------------------------------

TITLE: Complete Voice Agent Application Example (Python)
DESCRIPTION: This comprehensive Python script combines agent definition, tool usage, handoff logic, voice pipeline setup, and audio processing into a single runnable example. It demonstrates how to create a voice-enabled assistant that can use tools (like get_weather) and handoff to specialized agents (like spanish_agent) based on user input, processing audio from input to output.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/docs/voice/quickstart.md#_snippet_5

LANGUAGE: python
CODE:
```
import asyncio
import random

import numpy as np
import sounddevice as sd

from agents import (
    Agent,
    function_tool,
    set_tracing_disabled,
)
from agents.voice import (
    AudioInput,
    SingleAgentVoiceWorkflow,
    VoicePipeline,
)
from agents.extensions.handoff_prompt import prompt_with_handoff_instructions


@function_tool
def get_weather(city: str) -> str:
    """Get the weather for a given city."""
    print(f"[debug] get_weather called with city: {city}")
    choices = ["sunny", "cloudy", "rainy", "snowy"]
    return f"The weather in {city} is {random.choice(choices)}."


spanish_agent = Agent(
    name="Spanish",
    handoff_description="A spanish speaking agent.",
    instructions=prompt_with_handoff_instructions(
        "You're speaking to a human, so be polite and concise. Speak in Spanish.",
    ),
    model="gpt-4o-mini",
)

agent = Agent(
    name="Assistant",
    instructions=prompt_with_handoff_instructions(
        "You're speaking to a human, so be polite and concise. If the user speaks in Spanish, handoff to the spanish agent.",
    ),
    model="gpt-4o-mini",
    handoffs=[spanish_agent],
    tools=[get_weather],
)


async def main():
    pipeline = VoicePipeline(workflow=SingleAgentVoiceWorkflow(agent))
    buffer = np.zeros(24000 * 3, dtype=np.int16)
    audio_input = AudioInput(buffer=buffer)

    result = await pipeline.run(audio_input)

    # Create an audio player using `sounddevice`
    player = sd.OutputStream(samplerate=24000, channels=1, dtype=np.int16)
    player.start()

    # Play the audio stream as it comes in
    async for event in result.stream():
        if event.type == "voice_stream_event_audio":
            player.write(event.data)


if __name__ == "__main__":
    asyncio.run(main())
```

----------------------------------------

TITLE: Setting OpenAI API Key (Bash)
DESCRIPTION: This command sets your OpenAI API key as an environment variable. The Agents SDK uses this key to authenticate requests to the OpenAI API, enabling your agents to interact with models.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/docs/quickstart.md#_snippet_3

LANGUAGE: bash
CODE:
```
export OPENAI_API_KEY=sk-...
```

----------------------------------------

TITLE: Setting OpenAI API Key Environment Variable (Bash)
DESCRIPTION: Sets the `OPENAI_API_KEY` environment variable in the current shell session. The OpenAI Agents SDK requires this environment variable to authenticate with the OpenAI API. Replace `sk-...` with your actual API key.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/docs/ja/quickstart.md#_snippet_3

LANGUAGE: bash
CODE:
```
export OPENAI_API_KEY=sk-...
```

----------------------------------------

TITLE: Orchestrating Multiple Agents as Tools (Python)
DESCRIPTION: This snippet demonstrates how to create specialized agents and then expose them as tools to a central orchestrator agent. It shows how to define `Agent` instances for specific tasks (e.g., translation) and integrate them into another agent's `tools` list using the `as_tool` method. The `Runner.run` function is then used to execute the orchestrator agent with a given input, showcasing how it leverages its configured tools.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/docs/tools.md#_snippet_3

LANGUAGE: python
CODE:
```
from agents import Agent, Runner
import asyncio

spanish_agent = Agent(
    name="Spanish agent",
    instructions="You translate the user's message to Spanish",
)

french_agent = Agent(
    name="French agent",
    instructions="You translate the user's message to French",
)

orchestrator_agent = Agent(
    name="orchestrator_agent",
    instructions=(
        "You are a translation agent. You use the tools given to you to translate."
        "If asked for multiple translations, you call the relevant tools."
    ),
    tools=[
        spanish_agent.as_tool(
            tool_name="translate_to_spanish",
            tool_description="Translate the user's message to Spanish",
        ),
        french_agent.as_tool(
            tool_name="translate_to_french",
            tool_description="Translate the user's message to French",
        ),
    ],
)

async def main():
    result = await Runner.run(orchestrator_agent, input="Say 'Hello, how are you?' in Spanish.")
    print(result.final_output)
```

----------------------------------------

TITLE: Installing OpenAI Agents SDK (Bash)
DESCRIPTION: This snippet demonstrates how to install the OpenAI Agents SDK using the pip package manager. This is the essential first step to set up the SDK in your development environment.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/docs/index.md#_snippet_0

LANGUAGE: bash
CODE:
```
pip install openai-agents
```

----------------------------------------

TITLE: Installing OpenAI Agents SDK (Bash)
DESCRIPTION: This command installs the OpenAI Agents SDK into your active virtual environment using pip. This makes the `agents` library available for use in your Python project.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/docs/quickstart.md#_snippet_2

LANGUAGE: bash
CODE:
```
pip install openai-agents # or `uv add openai-agents`, etc
```

----------------------------------------

TITLE: Running a Basic Agent with OpenAI Agents SDK (Python)
DESCRIPTION: This example initializes a simple AI agent with specific instructions and uses the `Runner` class to execute a task synchronously. It illustrates the fundamental process of creating an `Agent` instance and retrieving its final output, showcasing a minimal agentic workflow.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/docs/index.md#_snippet_1

LANGUAGE: python
CODE:
```
from agents import Agent, Runner

agent = Agent(name="Assistant", instructions="You are a helpful assistant")

result = Runner.run_sync(agent, "Write a haiku about recursion in programming.")
print(result.final_output)
```

----------------------------------------

TITLE: Configuring Agent for Structured Pydantic Output (Python)
DESCRIPTION: This snippet shows how to configure an `Agent` to produce structured outputs using Pydantic models. By setting `output_type` to `CalendarEvent` (a Pydantic `BaseModel`), the agent is instructed to generate responses that conform to the defined schema, facilitating structured data extraction.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/docs/agents.md#_snippet_2

LANGUAGE: python
CODE:
```
from pydantic import BaseModel
from agents import Agent


class CalendarEvent(BaseModel):
    name: str
    date: str
    participants: list[str]

agent = Agent(
    name="Calendar extractor",
    instructions="Extract calendar events from text",
    output_type=CalendarEvent,
)
```

----------------------------------------

TITLE: Streaming Raw LLM Response Deltas with OpenAI Agents Python
DESCRIPTION: This snippet demonstrates how to stream raw LLM response events, specifically `ResponseTextDeltaEvent`, to output text token-by-token as it's generated. It uses `Runner.run_streamed()` and filters for `raw_response_event` types to print the `delta` content, providing immediate feedback from the LLM.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/docs/streaming.md#_snippet_0

LANGUAGE: python
CODE:
```
import asyncio
from openai.types.responses import ResponseTextDeltaEvent
from agents import Agent, Runner

async def main():
    agent = Agent(
        name="Joker",
        instructions="You are a helpful assistant.",
    )

    result = Runner.run_streamed(agent, input="Please tell me 5 jokes.")
    async for event in result.stream_events():
        if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
            print(event.data.delta, end="", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
```

----------------------------------------

TITLE: Installing OpenAI Agents SDK (Bash)
DESCRIPTION: Installs the OpenAI Agents Python SDK using pip (or another package manager like uv). This makes the `agents` library available for import and use within the active Python virtual environment.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/docs/ja/quickstart.md#_snippet_2

LANGUAGE: bash
CODE:
```
pip install openai-agents # or `uv add openai-agents`, etc
```

----------------------------------------

TITLE: Setting Default OpenAI API Key (Python)
DESCRIPTION: This snippet demonstrates how to programmatically set the default OpenAI API key using set_default_openai_key(). This is useful when the OPENAI_API_KEY environment variable cannot be set before the application starts. The key is used for LLM requests and tracing.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/docs/config.md#_snippet_0

LANGUAGE: Python
CODE:
```
from agents import set_default_openai_key

set_default_openai_key("sk-...")
```

----------------------------------------

TITLE: Defining Required Handoff Input Data (Python)
DESCRIPTION: Shows how to specify that a handoff expects structured input data from the LLM using the `input_type` parameter with a Pydantic `BaseModel`. When the LLM calls this handoff tool, it will attempt to generate arguments matching the `EscalationData` model, which are then passed to the `on_handoff` callback function.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/docs/ja/handoffs.md#_snippet_2

LANGUAGE: python
CODE:
```
from pydantic import BaseModel

from agents import Agent, handoff, RunContextWrapper

class EscalationData(BaseModel):
    reason: str

async def on_handoff(ctx: RunContextWrapper[None], input_data: EscalationData):
    print(f"Escalation agent called with reason: {input_data.reason}")

agent = Agent(name="Escalation agent")

handoff_obj = handoff(
    agent=agent,
    on_handoff=on_handoff,
    input_type=EscalationData,
)
```

----------------------------------------

TITLE: Defining Function Tools Automatically with Decorators - Python
DESCRIPTION: This snippet demonstrates how to define function tools using the @function_tool decorator. It shows how docstrings are used for descriptions and how function arguments are automatically converted into a JSON schema for tool parameters. It includes examples for both synchronous and asynchronous functions, and how to override tool names.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/docs/tools.md#_snippet_1

LANGUAGE: Python
CODE:
```
import json

from typing_extensions import TypedDict, Any

from agents import Agent, FunctionTool, RunContextWrapper, function_tool


class Location(TypedDict):
    lat: float
    long: float

@function_tool  # (1)!
async def fetch_weather(location: Location) -> str:
    # (2)!
    """Fetch the weather for a given location.

    Args:
        location: The location to fetch the weather for.
    """
    # In real life, we'd fetch the weather from a weather API
    return "sunny"


@function_tool(name_override="fetch_data")  # (3)!
def read_file(ctx: RunContextWrapper[Any], path: str, directory: str | None = None) -> str:
    """Read the contents of a file.

    Args:
        path: The path to the file to read.
        directory: The directory to read the file from.
    """
    # In real life, we'd read the file from the file system
    return "<file contents>"


agent = Agent(
    name="Assistant",
    tools=[fetch_weather, read_file],  # (4)!
)

for tool in agent.tools:
    if isinstance(tool, FunctionTool):
        print(tool.name)
        print(tool.description)
        print(json.dumps(tool.params_json_schema, indent=2))
        print()
```

----------------------------------------

TITLE: Orchestrating Agents with Handoffs (Python)
DESCRIPTION: This example demonstrates the use of `handoffs` to enable an agent to delegate tasks to specialized sub-agents. The `triage_agent` is configured with instructions to route user queries to either a `booking_agent` or a `refund_agent` based on the query's relevance, promoting modularity and specialization.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/docs/agents.md#_snippet_3

LANGUAGE: python
CODE:
```
from agents import Agent

booking_agent = Agent(...)
refund_agent = Agent(...)

triage_agent = Agent(
    name="Triage agent",
    instructions=(
        "Help the user with their questions."
        "If they ask about booking, handoff to the booking agent."
        "If they ask about refunds, handoff to the refund agent."
    ),
    handoffs=[booking_agent, refund_agent],
)
```

----------------------------------------

TITLE: Managing Multi-Turn Conversations with Agents in Python
DESCRIPTION: This example illustrates how to maintain a conversational thread across multiple turns using the `Runner.run()` method. It demonstrates using `result.to_input_list()` to capture the previous turn's context and append new user input for subsequent agent runs, simulating a continuous chat experience. Tracing is also enabled for the conversation.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/docs/running_agents.md#_snippet_1

LANGUAGE: Python
CODE:
```
async def main():
    agent = Agent(name="Assistant", instructions="Reply very concisely.")

    with trace(workflow_name="Conversation", group_id=thread_id):
        # First turn
        result = await Runner.run(agent, "What city is the Golden Gate Bridge in?")
        print(result.final_output)
        # San Francisco

        # Second turn
        new_input = result.to_input_list() + [{"role": "user", "content": "What state is it in?"}]
        result = await Runner.run(agent, new_input)
        print(result.final_output)
        # California
```

----------------------------------------

TITLE: Defining a Custom Input Guardrail Function (Python)
DESCRIPTION: Defines a Pydantic model `HomeworkOutput` and a `guardrail_agent` to check if input is homework. It then creates an asynchronous `homework_guardrail` function that uses the `guardrail_agent` to process input and returns a `GuardrailFunctionOutput` indicating if a "tripwire" (input is not homework) was triggered. Requires the `pydantic` library.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/docs/ja/quickstart.md#_snippet_8

LANGUAGE: python
CODE:
```
from agents import GuardrailFunctionOutput, Agent, Runner
from pydantic import BaseModel

class HomeworkOutput(BaseModel):
    is_homework: bool
    reasoning: str

guardrail_agent = Agent(
    name="Guardrail check",
    instructions="Check if the user is asking about homework.",
    output_type=HomeworkOutput,
)

async def homework_guardrail(ctx, agent, input_data):
    result = await Runner.run(guardrail_agent, input_data, context=ctx.context)
    final_output = result.final_output_as(HomeworkOutput)
    return GuardrailFunctionOutput(
        output_info=final_output,
        tripwire_triggered=not final_output.is_homework,
    )
```

----------------------------------------

TITLE: Streaming High-Level Agent Run and Item Events with OpenAI Agents Python
DESCRIPTION: This snippet illustrates how to stream higher-level events like `RunItemStreamEvent` and `AgentUpdatedStreamEvent`, ignoring raw response deltas. It shows how to detect and print updates when an agent changes or when an item (like a tool call, tool output, or message output) is fully generated, providing more structured progress updates.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/docs/streaming.md#_snippet_1

LANGUAGE: python
CODE:
```
import asyncio
import random
from agents import Agent, ItemHelpers, Runner, function_tool

@function_tool
def how_many_jokes() -> int:
    return random.randint(1, 10)


async def main():
    agent = Agent(
        name="Joker",
        instructions="First call the `how_many_jokes` tool, then tell that many jokes.",
        tools=[how_many_jokes],
    )

    result = Runner.run_streamed(
        agent,
        input="Hello",
    )
    print("=== Run starting ===")

    async for event in result.stream_events():
        # We'll ignore the raw responses event deltas
        if event.type == "raw_response_event":
            continue
        # When the agent updates, print that
        elif event.type == "agent_updated_stream_event":
            print(f"Agent updated: {event.new_agent.name}")
            continue
        # When items are generated, print them
        elif event.type == "run_item_stream_event":
            if event.item.type == "tool_call_item":
                print("-- Tool was called")
            elif event.item.type == "tool_call_output_item":
                print(f"-- Tool output: {event.item.output}")
            elif event.item.type == "message_output_item":
                print(f"-- Message output:\n {ItemHelpers.text_message_output(event.item)}")
            else:
                pass  # Ignore other event types

    print("=== Run complete ===")


if __name__ == "__main__":
    asyncio.run(main())
```

----------------------------------------

TITLE: Defining a Simple Agent (Python)
DESCRIPTION: Imports the `Agent` class from the `agents` library and creates a basic `Agent` instance named "Math Tutor". The agent is configured with instructions defining its role and behavior. Requires the `openai-agents` library installed.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/docs/ja/quickstart.md#_snippet_4

LANGUAGE: python
CODE:
```
from agents import Agent

agent = Agent(
    name="Math Tutor",
    instructions="You provide help with math problems. Explain your reasoning at each step and include examples",
)
```

----------------------------------------

TITLE: Running a Simple Agent Workflow (Python)
DESCRIPTION: Imports the `Runner` class and defines an asynchronous `main` function to execute a simple agent workflow. It calls `Runner.run()` with the `triage_agent` and an input query, then prints the final output received from the workflow.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/docs/ja/quickstart.md#_snippet_7

LANGUAGE: python
CODE:
```
from agents import Runner

async def main():
    result = await Runner.run(triage_agent, "What is the capital of France?")
    print(result.final_output)
```

----------------------------------------

TITLE: Example of Agent with LiteLLM Model Integration in Python
DESCRIPTION: This Python script demonstrates how to create an `Agent` using `LitellmModel` to interact with various AI providers. It includes a `function_tool` for weather information and prompts the user for a model name and API key, showcasing a complete agent setup and execution flow.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/docs/models/litellm.md#_snippet_1

LANGUAGE: python
CODE:
```
from __future__ import annotations

import asyncio

from agents import Agent, Runner, function_tool, set_tracing_disabled
from agents.extensions.models.litellm_model import LitellmModel

@function_tool
def get_weather(city: str):
    print(f"[debug] getting weather for {city}")
    return f"The weather in {city} is sunny."


async def main(model: str, api_key: str):
    agent = Agent(
        name="Assistant",
        instructions="You only respond in haikus.",
        model=LitellmModel(model=model, api_key=api_key),
        tools=[get_weather],
    )

    result = await Runner.run(agent, "What's the weather in Tokyo?")
    print(result.final_output)


if __name__ == "__main__":
    # First try to get model/api key from args
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, required=False)
    parser.add_argument("--api-key", type=str, required=False)
    args = parser.parse_args()

    model = args.model
    if not model:
        model = input("Enter a model name for Litellm: ")

    api_key = args.api_key
    if not api_key:
        api_key = input("Enter an API key for Litellm: ")

    asyncio.run(main(model, api_key))
```

----------------------------------------

TITLE: Creating Project Directory and Virtual Environment (Bash)
DESCRIPTION: Creates a new project directory, navigates into it, and sets up a Python virtual environment named `.venv` within the directory. This is a standard setup step for Python projects to isolate dependencies.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/docs/ja/quickstart.md#_snippet_0

LANGUAGE: bash
CODE:
```
mkdir my_project
cd my_project
python -m venv .venv
```

----------------------------------------

TITLE: Running a Complete Agent Workflow with Guardrails and Handoffs (Python)
DESCRIPTION: This comprehensive example integrates agent definitions, handoffs, and an input guardrail into a full asynchronous workflow. It demonstrates how to run the `triage_agent` with different user inputs, showcasing the routing and guardrail functionality in action.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/docs/quickstart.md#_snippet_9

LANGUAGE: python
CODE:
```
from agents import Agent, InputGuardrail, GuardrailFunctionOutput, Runner
from pydantic import BaseModel
import asyncio

class HomeworkOutput(BaseModel):
    is_homework: bool
    reasoning: str

guardrail_agent = Agent(
    name="Guardrail check",
    instructions="Check if the user is asking about homework.",
    output_type=HomeworkOutput,
)

math_tutor_agent = Agent(
    name="Math Tutor",
    handoff_description="Specialist agent for math questions",
    instructions="You provide help with math problems. Explain your reasoning at each step and include examples",
)

history_tutor_agent = Agent(
    name="History Tutor",
    handoff_description="Specialist agent for historical questions",
    instructions="You provide assistance with historical queries. Explain important events and context clearly.",
)


async def homework_guardrail(ctx, agent, input_data):
    result = await Runner.run(guardrail_agent, input_data, context=ctx.context)
    final_output = result.final_output_as(HomeworkOutput)
    return GuardrailFunctionOutput(
        output_info=final_output,
        tripwire_triggered=not final_output.is_homework,
    )

triage_agent = Agent(
    name="Triage Agent",
    instructions="You determine which agent to use based on the user's homework question",
    handoffs=[history_tutor_agent, math_tutor_agent],
    input_guardrails=[
        InputGuardrail(guardrail_function=homework_guardrail),
    ],
)

async def main():
    result = await Runner.run(triage_agent, "who was the first president of the united states?")
    print(result.final_output)

    result = await Runner.run(triage_agent, "what is life")
    print(result.final_output)

if __name__ == "__main__":
    asyncio.run(main())
```

----------------------------------------

TITLE: Running Full Agent Workflow with Input Guardrail and Handoffs (Python)
DESCRIPTION: Combines the definition of tutor agents, the guardrail agent and function, and the triage agent with an attached `InputGuardrail`. It then defines an `async def main()` function to run the triage agent with different inputs, demonstrating the guardrail and handoff logic. Includes `asyncio.run(main())` for executing the asynchronous workflow.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/docs/ja/quickstart.md#_snippet_9

LANGUAGE: python
CODE:
```
from agents import Agent, InputGuardrail, GuardrailFunctionOutput, Runner
from pydantic import BaseModel
import asyncio

class HomeworkOutput(BaseModel):
    is_homework: bool
    reasoning: str

guardrail_agent = Agent(
    name="Guardrail check",
    instructions="Check if the user is asking about homework.",
    output_type=HomeworkOutput,
)

math_tutor_agent = Agent(
    name="Math Tutor",
    handoff_description="Specialist agent for math questions",
    instructions="You provide help with math problems. Explain your reasoning at each step and include examples",
)

history_tutor_agent = Agent(
    name="History Tutor",
    handoff_description="Specialist agent for historical questions",
    instructions="You provide assistance with historical queries. Explain important events and context clearly.",
)


async def homework_guardrail(ctx, agent, input_data):
    result = await Runner.run(guardrail_agent, input_data, context=ctx.context)
    final_output = result.final_output_as(HomeworkOutput)
    return GuardrailFunctionOutput(
        output_info=final_output,
        tripwire_triggered=not final_output.is_homework,
    )

triage_agent = Agent(
    name="Triage Agent",
    instructions="You determine which agent to use based on the user's homework question",
    handoffs=[history_tutor_agent, math_tutor_agent],
    input_guardrails=[
        InputGuardrail(guardrail_function=homework_guardrail),
    ],
)

async def main():
    result = await Runner.run(triage_agent, "who was the first president of the united states?")
    print(result.final_output)

    result = await Runner.run(triage_agent, "what is life")
    print(result.final_output)

if __name__ == "__main__":
    asyncio.run(main())
```

----------------------------------------

TITLE: Applying Model Settings to an Agent in OpenAI Agents
DESCRIPTION: This snippet illustrates how to apply additional configuration parameters, such as 'temperature', to an Agent's model using 'ModelSettings'. This allows for fine-tuning the behavior of the underlying LLM beyond just selecting the model name, enabling more precise control over responses.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/docs/models/index.md#_snippet_3

LANGUAGE: python
CODE:
```
from agents import Agent, ModelSettings

english_agent = Agent(
    name="English agent",
    instructions="You only speak English",
    model="gpt-4o",
    model_settings=ModelSettings(temperature=0.1),
)
```

----------------------------------------

TITLE: Integrating Custom Functions as Tools
DESCRIPTION: This snippet demonstrates how to define and integrate custom Python functions as tools for an agent using the `@function_tool` decorator. The agent can then call these tools based on its instructions and user input, such as fetching weather information.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/README.md#_snippet_4

LANGUAGE: python
CODE:
```
import asyncio

from agents import Agent, Runner, function_tool


@function_tool
def get_weather(city: str) -> str:
    return f"The weather in {city} is sunny."


agent = Agent(
    name="Hello world",
    instructions="You are a helpful agent.",
    tools=[get_weather]
)


async def main():
    result = await Runner.run(agent, input="What's the weather in Tokyo?")
    print(result.final_output)
    # The weather in Tokyo is sunny.


if __name__ == "__main__":
    asyncio.run(main())
```

----------------------------------------

TITLE: Activating Python Virtual Environment (Bash)
DESCRIPTION: Activates the previously created Python virtual environment (`.venv`). This command makes the Python interpreter and installed packages within the virtual environment available in the current shell session. Must be run in each new terminal session.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/docs/ja/quickstart.md#_snippet_1

LANGUAGE: bash
CODE:
```
source .venv/bin/activate
```

----------------------------------------

TITLE: Defining Multiple Agents with Handoff Descriptions (Python)
DESCRIPTION: This code shows how to create multiple specialized `Agent` instances. Each agent includes a `handoff_description` which provides additional context, assisting a routing agent in determining the most appropriate agent for a given task.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/docs/quickstart.md#_snippet_5

LANGUAGE: python
CODE:
```
from agents import Agent

history_tutor_agent = Agent(
    name="History Tutor",
    handoff_description="Specialist agent for historical questions",
    instructions="You provide assistance with historical queries. Explain important events and context clearly.",
)

math_tutor_agent = Agent(
    name="Math Tutor",
    handoff_description="Specialist agent for math questions",
    instructions="You provide help with math problems. Explain your reasoning at each step and include examples",
)
```

----------------------------------------

TITLE: Defining Multiple Agents with Handoff Descriptions (Python)
DESCRIPTION: Demonstrates creating two distinct `Agent` instances, "History Tutor" and "Math Tutor". Each agent is given specific `instructions` and a `handoff_description` which is used by other agents for routing decisions in an orchestration.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/docs/ja/quickstart.md#_snippet_5

LANGUAGE: python
CODE:
```
from agents import Agent

history_tutor_agent = Agent(
    name="History Tutor",
    handoff_description="Specialist agent for historical questions",
    instructions="You provide assistance with historical queries. Explain important events and context clearly.",
)

math_tutor_agent = Agent(
    name="Math Tutor",
    handoff_description="Specialist agent for math questions",
    instructions="You provide help with math problems. Explain your reasoning at each step and include examples",
)
```

----------------------------------------

TITLE: Using LiteLLM-Prefixed Models with OpenAI Agents
DESCRIPTION: This code illustrates how to initialize Agent instances using models integrated via LiteLLM. It shows examples of configuring agents with Anthropic's Claude and Google's Gemini models by prefixing their names with 'litellm/', enabling access to a wide range of supported LLMs.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/docs/models/index.md#_snippet_1

LANGUAGE: python
CODE:
```
claude_agent = Agent(model="litellm/anthropic/claude-3-5-sonnet-20240620", ...)
gemini_agent = Agent(model="litellm/gemini/gemini-2.5-flash-preview-04-17", ...)
```

----------------------------------------

TITLE: Defining Agent Handoffs (Python)
DESCRIPTION: This snippet illustrates how to configure an agent, such as a 'Triage Agent', with a list of `handoffs`. This allows the agent to dynamically route tasks to other specified agents based on its instructions and the incoming query.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/docs/quickstart.md#_snippet_6

LANGUAGE: python
CODE:
```
triage_agent = Agent(
    name="Triage Agent",
    instructions="You determine which agent to use based on the user's homework question",
    handoffs=[history_tutor_agent, math_tutor_agent]
)
```

----------------------------------------

TITLE: Creating Basic Agent Handoffs (Python)
DESCRIPTION: This snippet demonstrates the basic ways to configure handoffs for an agent. You can either pass an `Agent` object directly to the `handoffs` list or use the `handoff()` function with the target agent. Both methods achieve the same result for a simple handoff.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/docs/ja/handoffs.md#_snippet_0

LANGUAGE: python
CODE:
```
from agents import Agent, handoff

billing_agent = Agent(name="Billing agent")
refund_agent = Agent(name="Refund agent")

# (1)!
triage_agent = Agent(name="Triage agent", handoffs=[billing_agent, handoff(refund_agent)])
```

----------------------------------------

TITLE: Creating a Basic Agent Handoff in Python
DESCRIPTION: This snippet demonstrates how to create a simple agent handoff. It initializes `billing_agent` and `refund_agent`, then configures `triage_agent` to hand off tasks to them. Handoffs can be specified directly as `Agent` objects or using the `handoff()` function for more control.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/docs/handoffs.md#_snippet_0

LANGUAGE: Python
CODE:
```
from agents import Agent, handoff

billing_agent = Agent(name="Billing agent")
refund_agent = Agent(name="Refund agent")

# (1)!
triage_agent = Agent(name="Triage agent", handoffs=[billing_agent, handoff(refund_agent)])
```

----------------------------------------

TITLE: Defining Agents with Tools and Handoffs (Python)
DESCRIPTION: This Python snippet defines two Agent instances: spanish_agent and agent. The agent includes a function_tool for get_weather and is configured to handoff to spanish_agent if the user speaks Spanish, demonstrating agent collaboration and tool usage within the SDK.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/docs/voice/quickstart.md#_snippet_2

LANGUAGE: python
CODE:
```
import asyncio
import random

from agents import (
    Agent,
    function_tool,
)
from agents.extensions.handoff_prompt import prompt_with_handoff_instructions



@function_tool
def get_weather(city: str) -> str:
    """Get the weather for a given city."""
    print(f"[debug] get_weather called with city: {city}")
    choices = ["sunny", "cloudy", "rainy", "snowy"]
    return f"The weather in {city} is {random.choice(choices)}."


spanish_agent = Agent(
    name="Spanish",
    handoff_description="A spanish speaking agent.",
    instructions=prompt_with_handoff_instructions(
        "You're speaking to a human, so be polite and concise. Speak in Spanish.",
    ),
    model="gpt-4o-mini",
)

agent = Agent(
    name="Assistant",
    instructions=prompt_with_handoff_instructions(
        "You're speaking to a human, so be polite and concise. If the user speaks in Spanish, handoff to the spanish agent.",
    ),
    model="gpt-4o-mini",
    handoffs=[spanish_agent],
    tools=[get_weather],
)
```

----------------------------------------

TITLE: Implementing Agent Handoffs
DESCRIPTION: This example illustrates how to configure multiple agents and use a 'triage' agent to hand off control to the appropriate agent based on the input language. It showcases asynchronous execution with `asyncio` and the `handoffs` parameter for agent routing.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/README.md#_snippet_3

LANGUAGE: python
CODE:
```
from agents import Agent, Runner
import asyncio

spanish_agent = Agent(
    name="Spanish agent",
    instructions="You only speak Spanish."
)

english_agent = Agent(
    name="English agent",
    instructions="You only speak English"
)

triage_agent = Agent(
    name="Triage agent",
    instructions="Handoff to the appropriate agent based on the language of the request.",
    handoffs=[spanish_agent, english_agent]
)


async def main():
    result = await Runner.run(triage_agent, input="Hola, ¿cómo estás?")
    print(result.final_output)
    # ¡Hola! Estoy bien, gracias por preguntar. ¿Y tú, cómo estás?


if __name__ == "__main__":
    asyncio.run(main())
```

----------------------------------------

TITLE: Running Agent Orchestration (Python)
DESCRIPTION: This asynchronous function demonstrates how to execute an agent workflow using the `Runner.run()` method. It initiates the process with a `triage_agent` and a specific query, then prints the final output generated by the orchestrated agents.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/docs/quickstart.md#_snippet_7

LANGUAGE: python
CODE:
```
from agents import Runner

async def main():
    result = await Runner.run(triage_agent, "What is the capital of France?")
    print(result.final_output)
```

----------------------------------------

TITLE: Defining an Agent with Handoff Destinations (Python)
DESCRIPTION: Creates a "Triage Agent" responsible for routing tasks to other agents. This agent is configured with a list of potential `handoffs`, which are other `Agent` instances it can transfer the task to based on its instructions and the input.
SOURCE: https://github.com/openai/openai-agents-python/blob/main/docs/ja/quickstart.md#_snippet_6

LANGUAGE: python
CODE:
```
triage_agent = Agent(
    name="Triage Agent",
    instructions="You determine which agent to use based on the user's homework question",
    handoffs=[history_tutor_agent, math_tutor_agent]
)
```