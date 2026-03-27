import os, anthropic
key = os.environ.get("ANTHROPIC_API_KEY", "")
print(f"Key prefix: {key[:20]}...")
client = anthropic.Anthropic(api_key=key)
for model in ["claude-haiku-4-5-20251001", "claude-sonnet-4-6", "claude-3-5-haiku-20241022"]:
    try:
        msg = client.messages.create(
            model=model, max_tokens=10,
            messages=[{"role": "user", "content": "hi"}]
        )
        print(f"SUCCESS with {model}:", msg.content)
        break
    except Exception as e:
        print(f"FAILED {model}: {e}")
