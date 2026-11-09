"""
MCP tool modules — in-process implementations.

All five in-process servers plus the permission layer.
Import from this package in agent base class (M3).
"""

from app.mcp_servers.permissions import (
    AGENT_PERMISSIONS,
    ALL_AGENT_IDS,
    PermissionDeniedError,
    check_permission,
)

__all__ = [
    "AGENT_PERMISSIONS",
    "ALL_AGENT_IDS",
    "PermissionDeniedError",
    "check_permission",
]
