"""Auth endpoints — implemented in Sub-task 4.1."""

from fastapi import APIRouter

router = APIRouter()


@router.post("/login")
async def login() -> dict:
    return {"status": "not_implemented", "milestone": "4.1"}


@router.get("/me")
async def me() -> dict:
    return {"status": "not_implemented", "milestone": "4.1"}
