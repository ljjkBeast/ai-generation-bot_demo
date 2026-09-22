import asyncio
import os

from dotenv import load_dotenv
from google import genai

load_dotenv()

gemini_client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

async def generate_text(provider: str, model: str, prompt: str):
    if provider == "google":
        response = await gemini_client.aio.models.generate_content(
            model=model,
            contents=prompt
        )

        print("TEXT:", response.text)
        usage = response.usage_metadata

        print("INPUT TOKENS:", usage.prompt_token_count)
        print("OUTPUT TOKENS:", usage.candidates_token_count)
        print("TOTAL TOKENS:", usage.total_token_count)

        return response.text

    await asyncio.sleep(5)

    return f"Generated: {prompt}"