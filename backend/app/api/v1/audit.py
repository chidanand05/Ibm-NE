"""Audit log endpoints — implemented in Sub-task 4.1."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_audit_logs() -> dict:
    return {"status": "not_implemented", "milestone": "4.1"}
