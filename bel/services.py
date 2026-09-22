import httpx

from fastapi import HTTPException

from database import charge_generation
from schemas import TelegramGenerationRequest


USA_URL = "http://127.0.0.1:8001"


async def start_generation(
    user_id: int,
    payload: TelegramGenerationRequest,
    cost: int
):
    user, generation, transaction, error = charge_generation(
        user_id,
        payload,
        cost
    )

    if error == "user_not_found":
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    if error == "not_enough_balance":
        raise HTTPException(
            status_code=400,
            detail="Not enough balance"
        )

    if error == "invalid_cost":
        raise HTTPException(
            status_code=400,
            detail="Invalid cost"
        )

    return generation


async def send_generation_to_usa(
    user_id: int,
    generation_id: int,
    provider: str,
    model: str,
    prompt: str
):
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{USA_URL}/generate",
            json={
                "user_id": user_id,
                "generation_id": generation_id,
                "provider": provider,
                "model": model,
                "prompt": prompt
            }
        )

    response.raise_for_status()

    return response.json()