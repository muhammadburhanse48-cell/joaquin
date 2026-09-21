import os
import anthropic
from dotenv import load_dotenv

load_dotenv(".env")

api_key = os.getenv("ANTHROPIC_API_KEY")
model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

if not api_key:
    print("Missing ANTHROPIC_API_KEY")
    raise SystemExit(1)

try:
    client = anthropic.Anthropic(api_key=api_key)

    response = client.messages.create(
        model=model,
        max_tokens=1,
        messages=[
            {"role": "user", "content": "Reply with OK"}
        ],
    )

    print("API key works and credits are available.")
    print(f"Model: {model}")
    print(f"Usage: {response.usage}")

except anthropic.AuthenticationError:
    print("Invalid or revoked API key.")
except anthropic.PermissionDeniedError:
    print("Permission denied. Check account access or billing.")
except anthropic.RateLimitError:
    print("Rate limited or quota exhausted.")
except anthropic.APIError as error:
    print(f"Anthropic API error: {error}")