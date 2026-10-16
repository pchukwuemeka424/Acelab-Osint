import json
import logging
import re

from app.config import Settings, get_settings
from app.security.ssrf import guarded_request

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
SYSTEM_PROMPT = (
    "You explain a phishing-infrastructure investigation using only the JSON evidence packet. "
    "Every factual sentence must cite an observation id that appears in the packet, written as [obs:ID]. "
    "If the packet does not support a conclusion, say that it does not. "
    "Do not invent owners, threat actors, IP relationships, certificates, or findings. "
    "Do not treat shared hosting, CDNs, public DNS, or certificate authorities as proof of common ownership. "
    "State that association scores are heuristic and not probabilities. "
    "Mention conflicting evidence and missing evidence when they are present in the packet."
)
OBS_RE = re.compile(r"\[obs:([A-Za-z0-9-]+)\]")


def maybe_narrate(packet: dict, settings: Settings | None = None, fetcher=None) -> tuple[str | None, str]:
    settings = settings or get_settings()
    if not settings.openrouter_api_key:
        return None, "skipped"
    fetcher = fetcher or guarded_request
    body = {
        "model": settings.openrouter_model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(packet, default=str)},
        ],
    }
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "HTTP-Referer": settings.openrouter_referer,
        "X-Title": "PIAE",
        "Content-Type": "application/json",
    }
    try:
        response = fetcher("POST", OPENROUTER_URL, "openrouter", headers=headers, json_body=body, timeout=40)
        payload = response.json()
        text = payload["choices"][0]["message"]["content"]
    except Exception:
        logger.warning("openrouter_narrative_failed")
        return None, "failed"
    if not isinstance(text, str) or not text.strip():
        return None, "failed"
    known = set(packet.get("observation_ids") or [])
    unknown = sorted({match for match in OBS_RE.findall(text) if match not in known})
    if unknown:
        text = (
            text.strip()
            + "\n\nNarrative contained references that do not match stored observations. "
            + "Those sentences are not findings."
        )
    return text.strip(), "generated"
