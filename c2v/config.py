"""Model IDs and settings. Import from here; never hard-code model strings elsewhere."""
from __future__ import annotations

import os
from pathlib import Path

def _load_dotenv() -> None:
    """Load KEY=VALUE lines from the repo's .env without overriding real env vars."""
    env = Path(__file__).resolve().parent.parent / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            if v.strip() and not os.environ.get(k.strip()):
                os.environ[k.strip()] = v.strip().strip('"').strip("'")


_load_dotenv()

MODEL_IDS = {
    "transcriber": "gemini-4-hydrogen",   # media -> Capture
    "router": "gemini-decision-1",        # Decisions API: type / folder / merge + confidence
    "manager": "gemini-4-neon",           # escalations, links, merges, final markdown
    "deep": "gemini-4-carbon",            # optional: hardest reconciliation only
    "agent": "antigravity-preview-09-2026",  # Managed Agent verifier
    "tts": "gemini-3.8-flash-tts",        # eval: render notes as noisy voice memos
}

REPO_ROOT = Path(__file__).resolve().parent.parent
VAULT_PATH = Path(os.environ.get("VAULT_PATH", REPO_ROOT / "demo_vault")).expanduser()
ROUTE_CONFIDENCE_MIN = float(os.environ.get("ROUTE_CONFIDENCE_MIN", "0.75"))


def clients():
    """Return (client, beta_client). Imported lazily so tests run without the SDK or a key."""
    from google import genai  # noqa: WPS433

    client = genai.Client()
    beta_client = genai.Client(http_options={"api_version": "v1beta"})
    return client, beta_client
