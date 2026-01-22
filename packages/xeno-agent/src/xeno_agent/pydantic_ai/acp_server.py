"""
ACP Server Implementation
Provides ACP (Agent Client Protocol) server for pydantic-ai agents
Supports HTTP and Stdio transports
"""

import asyncio
import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)


class ACPSessionManager:
    """In-memory session manager for ACP server."""

    def __init__(self):
        """Initialize in-memory session storage."""
        self._sessions: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def create(self, mcp_config: list[dict[str, Any]] | None = None) -> str:
        """
        Create a new session and return its ID.

        Args:
            mcp_config: Optional MCP server configuration

        Returns:
            Session ID (UUID string)
        """
        session_id = str(uuid.uuid4())

        async with self._lock:
            self._sessions[session_id] = {
                "id": session_id,
                "mcp_servers": mcp_config or [],
                "created_at": asyncio.get_event_loop().time(),
            }

        logger.debug(f"Created session: {session_id}")
        return session_id

    async def get(self, session_id: str) -> dict[str, Any] | None:
        """
        Retrieve session data by ID.

        Args:
            session_id: Session ID to retrieve

        Returns:
            Session data dict or None if not found
        """
        async with self._lock:
            return self._sessions.get(session_id)

    async def delete(self, session_id: str) -> None:
        """
        Delete a session by ID.

        Args:
            session_id: Session ID to delete
        """
        async with self._lock:
            if session_id in self._sessions:
                session_data = self._sessions.pop(session_id)
                logger.debug(f"Deleted session: {session_id}")
                return session_data
            return None

    async def list_all(self) -> list[str]:
        """
        List all active session IDs.

        Returns:
            List of session IDs
        """
        async with self._lock:
            return list(self._sessions.keys())

    async def update(self, session_id: str, data: dict[str, Any]) -> None:
        """
        Update session data.

        Args:
            session_id: Session ID to update
            data: Data to merge into session
        """
        async with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id].update(data)
                logger.debug(f"Updated session: {session_id}")
