"""
Optional convenience script: creates the Vapi assistant from assistant_config.json
via the Vapi API, and prints next steps for getting a phone number.

You do NOT need this script — you can do everything it does by hand in the Vapi
dashboard (see README.md "Vapi setup" section), which is arguably faster for a
first-time setup since the dashboard UI validates your JSON as you go.

Usage:
    export VAPI_API_KEY=...
    export PUBLIC_BASE_URL=https://your-app.up.railway.app
    python scripts/setup_vapi.py
"""
import json
import os
import sys
from pathlib import Path

import httpx

VAPI_API_KEY = os.getenv("VAPI_API_KEY")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL")
CONFIG_PATH = Path(__file__).parent.parent / "vapi" / "assistant_config.json"
PROMPT_PATH = Path(__file__).parent.parent / "vapi" / "system_prompt.md"


def extract_prompt_block(markdown: str) -> str:
    """Pull the ```-fenced prompt block out of system_prompt.md."""
    start = markdown.find("```\nYou are Ava")
    if start == -1:
        raise RuntimeError("Could not find prompt block in system_prompt.md")
    start += 4  # skip the fence
    end = markdown.find("```", start)
    return markdown[start:end].strip()


def main():
    if not VAPI_API_KEY:
        sys.exit("Set VAPI_API_KEY first.")
    if not PUBLIC_BASE_URL:
        sys.exit("Set PUBLIC_BASE_URL first (your deployed API's base URL, e.g. https://x.up.railway.app).")

    config = json.loads(CONFIG_PATH.read_text())
    prompt = extract_prompt_block(PROMPT_PATH.read_text())
    config["model"]["systemPrompt"] = prompt

    # Wire the real webhook URLs in place of the placeholders.
    for tool in config["model"]["tools"]:
        tool["server"]["url"] = f"{PUBLIC_BASE_URL}/vapi/tool-calls"
        tool["server"].pop("credentialId", None)  # simplest path: no auth for first test
    config["server"]["url"] = f"{PUBLIC_BASE_URL}/vapi/call-events"
    config["server"].pop("credentialId", None)

    resp = httpx.post(
        "https://api.vapi.ai/assistant",
        headers={"Authorization": f"Bearer {VAPI_API_KEY}", "Content-Type": "application/json"},
        json=config,
        timeout=30,
    )
    resp.raise_for_status()
    assistant = resp.json()
    print(f"Created assistant: {assistant['id']}")
    print()
    print("Next step — get a phone number:")
    print("  Free Vapi number: https://dashboard.vapi.ai -> Phone Numbers -> Create -> Free Vapi Number")
    print(f"  Then assign assistant '{assistant['id']}' as its inbound assistant.")
    print()
    print("Reminder: this script skipped webhook auth (credentialId) for speed.")
    print("Add a Bearer Token credential in the dashboard and set VAPI_WEBHOOK_SECRET")
    print("in your deployed app before sending real traffic.")


if __name__ == "__main__":
    main()
