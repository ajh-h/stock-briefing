#!/bin/bash
read -p "Paste your API key: " KEY
python3 - <<EOF
import anthropic
try:
    c = anthropic.Anthropic(api_key="$KEY")
    m = c.messages.create(model="claude-haiku-4-5-20251001", max_tokens=5, messages=[{"role":"user","content":"hi"}])
    print("SUCCESS - credits working!")
except Exception as e:
    print("FAILED:", e)
EOF
