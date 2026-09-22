from aiohttp import web
from services import generate_text
import httpx

async def run_generation(data):
    try:
        result = await generate_text(
            provider=data["provider"],
            model=data["model"],
            prompt=data["prompt"]
        )

        print("Result:", result)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"http://127.0.0.1:8000/internal/"
                f"generations/{data['generation_id']}/complete",
                json={
                    "status": "completed",
                    "result": result
                }
            )

        response.raise_for_status()

        print("BEL updated:", response.json())

    except Exception as e:
        print("Generation failed:", e)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"http://127.0.0.1:8000/internal/"
                f"generations/{data['generation_id']}/complete",
                json={
                    "status": "failed",
                    "result": None
                }
            )

        response.raise_for_status()


async def generate(request):
    data = await request.json()

    print("Received from BEL:", data)

    # Запускаем генерацию в фоне
    import asyncio

    asyncio.create_task(
        run_generation(data)
    )

    # Не ждём 5 секунд
    return web.json_response({
        "status": "accepted",
        "message": "Generation started"
    })


app = web.Application()

app.router.add_post(
    "/generate",
    generate
)


if __name__ == "__main__":
    web.run_app(
        app,
        host="127.0.0.1",
        port=8001
    )