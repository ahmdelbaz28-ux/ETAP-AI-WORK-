"""
Smithery MCP Integration for AhmedETAP
Connects the platform to Model Context Protocol servers via Smithery.

MCP allows AI agents to call external tools (databases, APIs, simulators)
in a standardized way. Smithery is the registry/gateway for MCP servers.

Docs: https://smithery.ai/docs
"""

import logging
import os
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


class SmitheryClient:
    """
    Client for Smithery MCP server registry.
    Enables AhmedETAP agents to discover and call external MCP tools.
    """

    BASE_URL = "https://api.smithery.ai"

    def __init__(self):
        self.api_key = os.getenv("SMITHERY_API_KEY", "")
        self.enabled = bool(self.api_key)
        self.base_url = os.getenv("SMITHERY_BASE_URL", self.BASE_URL)

        if self.enabled:
            logger.info("✅ Smithery MCP client initialized")
        else:
            logger.info("Smithery disabled: SMITHERY_API_KEY not set")

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "AhmedETAP/1.0.0",
        }

    async def list_servers(self, query: Optional[str] = None) -> list[dict]:
        """List available MCP servers from Smithery registry."""
        if not self.enabled:
            return []
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                params = {"q": query} if query else {}
                resp = await client.get(
                    f"{self.base_url}/v1/servers",
                    headers=self._headers,
                    params=params,
                )
                resp.raise_for_status()
                return resp.json().get("servers", [])
        except Exception as e:
            logger.warning(f"Smithery list_servers error (non-critical): {e}")
            return []

    async def call_tool(
        self,
        server_id: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Call a specific tool on an MCP server via Smithery.

        Args:
            server_id: The Smithery server identifier (e.g., 'filesystem', 'postgres')
            tool_name: The MCP tool name to call
            arguments: Tool input arguments

        Returns:
            Tool execution result dict
        """
        if not self.enabled:
            return {"error": "Smithery not configured", "result": None}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                payload = {
                    "server_id": server_id,
                    "tool": tool_name,
                    "arguments": arguments,
                }
                resp = await client.post(
                    f"{self.base_url}/v1/call",
                    headers=self._headers,
                    json=payload,
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Smithery call_tool HTTP error: {e.response.status_code}")
            return {"error": str(e), "result": None}
        except Exception as e:
            logger.error(f"Smithery call_tool error: {e}")
            return {"error": str(e), "result": None}

    def health_check(self) -> dict:
        """Return Smithery integration status."""
        return {
            "enabled": self.enabled,
            "base_url": self.base_url,
            "dashboard": "https://smithery.ai/console",
        }


# ─── MCP Tool Registry for AhmedETAP agents ──────────────────────────────────
class ETAPMCPRegistry:
    """
    Registry of MCP tools available to AhmedETAP agents.
    Maps engineering operations to Smithery MCP server calls.
    """

    def __init__(self, client: SmitheryClient):
        self.client = client

    async def query_standards_database(self, standard: str, query: str) -> dict:
        """Query IEEE/IEC standards database via MCP."""
        return await self.client.call_tool(
            server_id="etap-standards-db",
            tool_name="query",
            arguments={"standard": standard, "query": query},
        )

    async def fetch_equipment_datasheet(self, equipment_id: str) -> dict:
        """Fetch equipment technical specifications via MCP."""
        return await self.client.call_tool(
            server_id="equipment-catalog",
            tool_name="get_datasheet",
            arguments={"equipment_id": equipment_id},
        )

    async def export_report(self, report_data: dict, format: str = "pdf") -> dict:
        """Export engineering report via MCP file tool."""
        return await self.client.call_tool(
            server_id="report-generator",
            tool_name="export",
            arguments={"data": report_data, "format": format},
        )


# ─── Module-level singletons ─────────────────────────────────────────────────
smithery_client = SmitheryClient()
mcp_registry = ETAPMCPRegistry(smithery_client)
