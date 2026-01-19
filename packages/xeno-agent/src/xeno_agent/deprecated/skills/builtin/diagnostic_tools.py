"""
Diagnostic simulation tools for fault diagnosis scenario.

These tools simulate real system operations without actually calling
external systems. They return realistic mock data for testing.
"""

import json

from crewai.tools import BaseTool

from ...core.tool_decorator import configured_tool


@configured_tool("collect_metrics")
class CollectMetricsTool(BaseTool):
    """Simulate collecting system metrics."""

    # name and description are injected by @configured_tool

    def _run(self, metric_types: str = "all") -> str:
        """
        Collect system metrics from various sources.

        Args:
            metric_types: Types of metrics to collect (cpu, memory, errors, latency, all)

        Returns:
            JSON string of collected metrics
        """
        # Mock response - in production, this would query real monitoring systems
        mock_data = {
            "cpu": {"usage": 85.3, "peak": 92.1},
            "memory": {"usage": 78.5, "available_gb": 2.3},
            "errors": {"rate": 0.05, "top_errors": ["timeout", "null_pointer"]},
            "latency": {"p50": 120, "p95": 450, "p99": 890},
            "timestamp": "2026-01-18T10:30:00Z",
        }

        if metric_types != "all":
            # Filter by requested type
            return json.dumps({k: v for k, v in mock_data.items() if metric_types.lower() in k.lower()})

        return json.dumps(mock_data, indent=2, ensure_ascii=False)


@configured_tool("query_logs")
class QueryLogsTool(BaseTool):
    """Simulate querying system logs."""

    def _run(self, time_range: str = "1h", keywords: str = "") -> str:
        """
        Query system logs for relevant entries.

        Args:
            time_range: Time range to query (e.g., "1h", "24h")
            keywords: Keywords to filter logs

        Returns:
            Relevant log entries
        """
        # Mock logs
        mock_logs = [
            {"timestamp": "2026-01-18T10:15:00Z", "level": "ERROR", "service": "api-gateway", "message": "Connection timeout to downstream service", "correlation_id": "abc123"},
            {
                "timestamp": "2026-01-18T10:17:23Z",
                "level": "WARNING",
                "service": "database",
                "message": "Slow query detected: SELECT * FROM users WHERE id = ?",
                "correlation_id": "abc124",
            },
            {"timestamp": "2026-01-18T10:20:45Z", "level": "ERROR", "service": "auth-service", "message": "Null pointer exception in user validation", "correlation_id": "abc125"},
        ]

        if keywords:
            mock_logs = [log for log in mock_logs if keywords.lower() in log["message"].lower()]

        return json.dumps(mock_logs, indent=2, ensure_ascii=False)


@configured_tool("query_knowledge_base")
class QueryKnowledgeBaseTool(BaseTool):
    """Simulate querying diagnostic knowledge base."""

    def _run(self, query: str) -> str:
        """
        Query knowledge base for relevant information.

        Args:
            query: Search query for knowledge base

        Returns:
            Relevant knowledge base entries
        """
        # Mock knowledge base
        mock_kb = [
            {
                "symptoms": ["Connection timeout", "High latency"],
                "root_cause": "Database connection pool exhaustion",
                "solution": "Increase connection pool size and implement connection leak detection",
                "confidence": 0.85,
                "case_id": "KB-2024-001",
            },
            {
                "symptoms": ["Null pointer", "Validation errors"],
                "root_cause": "Missing null check in user validation",
                "solution": "Add null validation before accessing user object",
                "confidence": 0.92,
                "case_id": "KB-2024-015",
            },
            {
                "symptoms": ["High CPU usage", "Memory leaks"],
                "root_cause": "Inefficient algorithm in data processing",
                "solution": "Optimize algorithm with better time complexity",
                "confidence": 0.78,
                "case_id": "KB-2024-023",
            },
        ]

        # Simple keyword matching
        results = []
        query_lower = query.lower()
        for entry in mock_kb:
            score = sum(1 for symptom in entry["symptoms"] if any(word in query_lower for word in symptom.lower().split()))
            if score > 0:
                results.append({**entry, "match_score": score})

        return json.dumps(results, indent=2, ensure_ascii=False)


@configured_tool("deep_inspect")
class DeepInspectTool(BaseTool):
    """Simulate deep inspection of system components."""

    def _run(self, component: str, inspection_type: str = "status") -> str:
        """
        Perform deep inspection of a system component.

        Args:
            component: Component to inspect (e.g., "database", "api-gateway")
            inspection_type: Type of inspection (status, config, dependencies)

        Returns:
            Detailed inspection results
        """
        # Mock inspection results
        mock_results = {
            "database": {
                "status": {
                    "connection_pool": {"active": 95, "max": 100, "exhausted": True},
                    "replication": {"lag": 0, "status": "healthy"},
                    "storage": {"used_percent": 82, "available_gb": 180},
                },
                "config": {"pool_size": 100, "timeout": 30, "max_connections": 100},
            },
            "api-gateway": {"status": {"health": "degraded", "rate_limit": {"current": 850, "limit": 1000}, "dependencies": {"auth-service": "OK", "database": "SLOW"}}},
        }

        result = mock_results.get(component, {"error": f"Component {component} not found"})
        return json.dumps(result, indent=2, ensure_ascii=False)
