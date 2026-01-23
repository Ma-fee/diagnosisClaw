import asyncio

import pytest

from xeno_agent.pydantic_ai.acp_legacy import ACPAgentRuntime, ACPClient, Transport


class MockTransport(Transport):
    def __init__(self):
        self.sent_messages = []
        self.receive_queue = asyncio.Queue()

    async def send(self, message):
        self.sent_messages.append(message)

        # Automatic response for testing
        if message.get("method") == "prompt/message":
            await self.receive_queue.put({"jsonrpc": "2.0", "result": {"content": "Hello from ACP!"}, "id": message.get("id")})
        elif message.get("method") == "client/request" and message.get("params", {}).get("method") == "tools/list":
            await self.receive_queue.put(
                {
                    "jsonrpc": "2.0",
                    "result": {"tools": [{"name": "test_tool", "description": "A test tool", "parameters": {"type": "object", "properties": {}}}]},
                    "id": message.get("id"),
                },
            )

    async def receive(self):
        return await self.receive_queue.get()

    async def close(self):
        pass


@pytest.mark.asyncio
async def test_acp_client_get_tools():
    transport = MockTransport()
    client = ACPClient(transport)

    # Start background message handling
    task = asyncio.create_task(client.handle_messages())

    try:
        tools = await client.get_available_tools()
        assert len(tools) == 1
        assert tools[0].name == "test_tool"
    finally:
        task.cancel()


@pytest.mark.asyncio
async def test_acp_agent_runtime_invoke():
    transport = MockTransport()
    client = ACPClient(transport)
    runtime = ACPAgentRuntime(client)

    # Start background message handling
    task = asyncio.create_task(client.handle_messages())

    try:
        result = await runtime.invoke("agent-1", "Hello")
        assert result.data == "Hello from ACP!"
        assert transport.sent_messages[0]["method"] == "prompt/message"
    finally:
        task.cancel()


@pytest.mark.asyncio
async def test_acp_conversion_logic():
    transport = MockTransport()
    client = ACPClient(transport)

    req = client.to_agent_request("test_tool", {"arg1": "val1"})
    assert req.method == "test_tool"
    assert req.params == {"arg1": "val1"}

    res_data = {"jsonrpc": "2.0", "result": "success", "id": "123"}
    result = client.from_agent_response(res_data)
    assert result == "success"
