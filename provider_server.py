from fastapi import FastAPI
import asyncio

app = FastAPI()


@app.post("/generate")
async def generate():
    print("Provider: generation started")

    await asyncio.sleep(5)

    print("Provider: generation finished")

    return {
        "result": "Image generated"
    }