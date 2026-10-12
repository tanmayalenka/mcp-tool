import asyncio
import json
import sys
from pathlib import Path

import ollama
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    server_path = str(Path(__file__).with_name("server.py"))

    # Launch and connect to the MCP server.
    params = StdioServerParameters(
        command=sys.executable,
        args=[server_path],
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Discover tools dynamically from MCP.
            result = await session.list_tools()

            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or "",
                        "parameters": tool.inputSchema,
                    },
                }
                for tool in result.tools
            ]

            messages = [
                {
                    "role": "user",
                    "content": "What is 125 multiplied by 24?",
                }
            ]

            # Let the model decide which tool to call.
            while True:
                response = ollama.chat(
                    model="llama3.1:8b",
                    messages=messages,
                    tools=tools,
                )

                messages.append(response.message)

                calls = response.message.tool_calls or []

                # No more tool calls: show the final answer.
                if not calls:
                    print(response.message.content)
                    break

                for call in calls:
                    name = call.function.name
                    args = call.function.arguments

                    print(f"Calling MCP tool: {name}({args})")

                    # Execute the requested tool on the MCP server.
                    tool_result = await session.call_tool(
                        name,
                        arguments=args,
                    )

                    # Convert MCP content blocks to text.
                    output = "\n".join(
                        item.text
                        for item in tool_result.content
                        if hasattr(item, "text")
                    )

                    if tool_result.isError:
                        output = f"Tool error: {output}"

                    # Send the result back to Ollama.
                    messages.append({
                        "role": "tool",
                        "tool_name": name,
                        "content": output or json.dumps(
                            tool_result.structuredContent
                        ) if tool_result.structuredContent else output,
                    })


if __name__ == "__main__":
    asyncio.run(main())