# tinyagent/cli.py
"""
Command-Line Interface for TinyAgent.
"""

import argparse

async def main():
    parser = argparse.ArgumentParser(description="TinyAgent: A multi-step agent framework.")
    parser.add_argument("task", help="The task for the agent to perform (e.g., 'generate_prd').")
    parser.add_argument("--input", help="Path to an input file for the task.")
    parser.add_argument("--output", help="Path to save the output of the task.")
    # Add other relevant arguments

    args = parser.parse_args()

    print(f"TinyAgent CLI started.")
    print(f"Task: {args.task}")
    if args.input:
        print(f"Input file: {args.input}")
    if args.output:
        print(f"Output file: {args.output}")

    # Initialize AgentCore and run the task
    # config = load_configuration() # Placeholder
    # agent = AgentCore(config)
    # result = await agent.run_task(args.task_description or args.input)
    # print(f"Agent Result: {result}")
    # if args.output: save_output(result, args.output)

if __name__ == '__main__':
    # import asyncio
    # asyncio.run(main())
    print("CLI placeholder executed. Uncomment asyncio lines to run full CLI.") 