import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

from xeno_agent.pydantic_ai.interfaces import AgentResult, AgentRuntime

logger = logging.getLogger(__name__)


class ACPTool(BaseModel):
    """ACP Tool definition."""

    name: str
    description: str
    input_schema: dict[str, Any] = Field(alias="parameters")

    class Config:
        populate_by_name = True


class AgentRequest(BaseModel):
    """ACP Agent Request (e.g. for tool calling)."""

    method: str
    params: dict[str, Any] = Field(default_factory=dict)
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class AgentResponse(BaseModel):
    """ACP Agent Response."""

    result: Any = None
    error: dict[str, Any] | None = None
    id: str


class Transport(ABC):
    """Abstract base class for ACP transports."""

    @abstractmethod
    async def send(self, message: dict[str, Any]) -> None:
        """Send a message."""

    @abstractmethod
    async def receive(self) -> dict[str, Any]:
        """Receive a message."""

    @abstractmethod
    async def close(self) -> None:
        """Close the transport."""


class HttpTransport(Transport):
    """HTTP transport for ACP using httpx."""

    def __init__(self, base_url: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)
        self._receive_queue: asyncio.Queue = asyncio.Queue()

    async def send(self, message: dict[str, Any]) -> None:
        """Send a message via HTTP POST."""
        try:
            response = await self.client.post("/rpc", json=message)
            response.raise_for_status()

            if response.content:
                await self._receive_queue.put(response.json())
        except httpx.HTTPError as e:
            await self._receive_queue.put(
                {
                    "jsonrpc": "2.0",
                    "error": {"code": -32000, "message": str(e)},
                    "id": message.get("id"),
                },
            )

    async def receive(self) -> dict[str, Any]:
        """Receive a message from the queue."""
        return await self._receive_queue.get()

    async def close(self) -> None:
        """Close the httpx client."""
        await self.client.aclose()


@dataclass
class ACPClient:
    """ACP Client for communication with remote agents/tools."""

    transport: Transport
    request_handlers: dict[str, Callable] = field(default_factory=dict)
    pending_requests: dict[str, asyncio.Future] = field(default_factory=dict)

    async def send_request(
        self,
        method: str,
        params: dict[str, Any],
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Send a JSON-RPC 2.0 request and wait for the response."""
        rid = request_id or str(uuid.uuid4())
        future: asyncio.Future[dict[str, Any]] = asyncio.Future()
        self.pending_requests[rid] = future

        message = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": rid,
        }

        await self.transport.send(message)
        return await future

    async def send_notification(self, method: str, params: dict[str, Any]) -> None:
        """Send a JSON-RPC 2.0 notification."""
        message = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        await self.transport.send(message)

    def register_handler(self, method: str, handler: Callable) -> None:
        """Register a handler for a remote request or notification."""
        self.request_handlers[method] = handler

    def to_agent_request(self, method: str, params: dict[str, Any]) -> AgentRequest:
        """Convert a tool call to an ACP AgentRequest."""
        return AgentRequest(method=method, params=params)

    def from_agent_response(self, response_data: dict[str, Any]) -> Any:
        """Convert an ACP AgentResponse back to a result."""
        response = AgentResponse.model_validate(response_data)
        if response.error:
            msg = response.error.get("message", "Unknown error")
            raise RuntimeError(f"ACP Error: {msg}")
        return response.result

    async def get_available_tools(self) -> list[ACPTool]:
        """Query the remote server for available tools."""
        response = await self.send_request(
            method="client/request",
            params={
                "method": "tools/list",
                "params": {},
            },
        )

        if "error" in response:
            raise RuntimeError(f"Failed to get tools: {response['error']}")

        tools_data = response.get("result", {}).get("tools", [])
        return [ACPTool.model_validate(t) for t in tools_data]

    async def handle_messages(self) -> None:
        """Background task to handle incoming messages from the transport."""
        try:
            while True:
                message = await self.transport.receive()
                await self._process_message(message)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Error in ACP handle_messages")

    async def _process_message(self, message: dict[str, Any]) -> None:
        """Process an incoming JSON-RPC message."""
        rid = message.get("id")

        if rid in self.pending_requests:
            future = self.pending_requests.pop(rid)
            if not future.done():
                future.set_result(message)
            return

        method = message.get("method")
        if not method:
            return

        handler = self.request_handlers.get(method)
        if not handler:
            if rid:
                await self.transport.send(
                    {
                        "jsonrpc": "2.0",
                        "error": {"code": -32601, "message": f"Method not found: {method}"},
                        "id": rid,
                    },
                )
            return

        try:
            result = await handler(message.get("params", {}))
            if rid:
                await self.transport.send(
                    {
                        "jsonrpc": "2.0",
                        "result": result,
                        "id": rid,
                    },
                )
        except Exception as e:  # noqa: BLE001
            if rid:
                await self.transport.send(
                    {
                        "jsonrpc": "2.0",
                        "error": {"code": -32000, "message": str(e)},
                        "id": rid,
                    },
                )


class ACPBridgeToolset:
    """Bridges remote ACP tools to a PydanticAI agent."""

    def __init__(self, client: ACPClient):
        self.client = client
        self.bridged_tools: dict[str, ACPTool] = {}

    async def sync_tools(self) -> list[str]:
        """Fetch remote tools and update the bridged set."""
        tools = await self.client.get_available_tools()
        self.bridged_tools = {t.name: t for t in tools}
        return list(self.bridged_tools.keys())

    def attach_to_agent(self, agent: Agent) -> None:
        """Attach all bridged tools to the PydanticAI agent."""
        for tool_name in self.bridged_tools:
            # We use a closure to capture the tool name
            def make_tool(name: str):
                async def remote_tool_wrapper(ctx: RunContext[Any], **kwargs: Any) -> Any:
                    # Translate PydanticAI tool call to ACP agent/request
                    response = await self.client.send_request(
                        method="agent/request",
                        params={
                            "method": f"tools/call/{name}",
                            "params": kwargs,
                        },
                    )
                    return self.client.from_agent_response(response)

                # Set metadata for PydanticAI to pick up
                remote_tool_wrapper.__name__ = name
                remote_tool_wrapper.__doc__ = self.bridged_tools[name].description
                return remote_tool_wrapper

            agent.tool(make_tool(tool_name))


class ACPBridgeHooks:
    """Hooks to notify ACP about PydanticAI tool lifecycle events."""

    def __init__(self, client: ACPClient):
        self.client = client

    async def on_tool_call_start(self, tool_name: str, call_id: str, params: dict[str, Any]) -> None:
        """Notify ACP that a tool call has started."""
        await self.client.send_notification(
            method="session/update",
            params={
                "type": "tool_call",
                "status": "pending",
                "tool_name": tool_name,
                "call_id": call_id,
                "input": params,
            },
        )

    async def on_tool_call_complete(self, tool_name: str, call_id: str, result: Any) -> None:
        """Notify ACP that a tool call has finished."""
        await self.client.send_notification(
            method="session/update",
            params={
                "type": "tool_call",
                "status": "completed",
                "tool_name": tool_name,
                "call_id": call_id,
                "output": result,
            },
        )


class ACPAgentRuntime(AgentRuntime):
    """Remote Agent Runtime using ACP protocol."""

    def __init__(self, client: ACPClient):
        self.client = client

    async def invoke(self, agent_id: str, message: str, **kwargs: Any) -> AgentResult:
        """Invoke a remote agent via ACP."""
        response = await self.send_request(
            method="prompt/message",
            params={
                "agent_id": agent_id,
                "message": message,
                "context": kwargs.get("context", {}),
            },
        )

        if "error" in response:
            raise RuntimeError(f"ACP Invoke Error: {response['error']}")

        result_data = response.get("result", {})
        return AgentResult(data=result_data.get("content", ""), metadata={"acp_response": result_data})

    async def send_request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Proxy to client.send_request."""
        return await self.client.send_request(method, params)

    async def delegate(self, target_agent: str, task: str, **kwargs: Any) -> AgentResult:
        """Delegate to a remote agent via ACP."""
        return await self.invoke(target_agent, task, **kwargs)
