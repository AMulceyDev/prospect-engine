from __future__ import annotations

import json
import logging

import requests

logger = logging.getLogger(__name__)

_PROMPT_OWNERSHIP_AND_QUALITY = """\
You are analysing a website to determine whether it belongs to a specific company and to assess its quality.

Target company:
- Name: {name}
- SIREN: {siren}
- City: {commune}

Page content (excerpt):
{text}

Respond ONLY with valid JSON containing these fields:
- "ownership": true if this site belongs to this company, false otherwise
- "ownership_reason": a short sentence explaining your decision
- "score": integer 1-10 rating the site quality (10 = modern/professional), null if ownership=false
- "obsolete": true if the site appears outdated or abandoned, null if ownership=false
- "verdict": one sentence summarising the site state, null if ownership=false
"""

_PROMPT_QUALITY_ONLY = """\
You are assessing the quality of a company website for commercial prospecting purposes.

Company: {name}

Page content (excerpt):
{text}

Respond ONLY with valid JSON containing these fields:
- "score": integer 1-10 rating the site quality (10 = modern/professional)
- "obsolete": true if the site appears outdated or abandoned, false otherwise
- "verdict": one sentence summarising the site state
"""


def _call(prompt: str, ollama_url: str, model: str, timeout: float) -> dict:
    resp = requests.post(
        f"{ollama_url}/api/chat",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "format": "json",
            "stream": False,
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    return json.loads(resp.json()["message"]["content"])


def judge_ownership_and_quality(
    page_text: str,
    company_name: str | None,
    company_siren: str | None,
    company_commune: str | None,
    ollama_url: str,
    model: str,
    timeout: float = 180.0,
) -> dict:
    prompt = _PROMPT_OWNERSHIP_AND_QUALITY.format(
        name=company_name or "unknown",
        siren=company_siren or "unknown",
        commune=company_commune or "unknown",
        text=page_text[:3000],
    )
    try:
        result = _call(prompt, ollama_url, model, timeout)
        return {
            "ownership": bool(result.get("ownership", False)),
            "ownership_reason": str(result.get("ownership_reason", "")),
            "score": int(result["score"]) if result.get("score") is not None else None,
            "obsolete": result.get("obsolete"),
            "verdict": result.get("verdict"),
        }
    except Exception as exc:
        logger.warning("LLM unavailable: %s", exc)
        return {"ownership": False, "ownership_reason": None, "score": None, "obsolete": None, "verdict": None}


def judge_quality(
    page_text: str,
    company_name: str | None,
    ollama_url: str,
    model: str,
    timeout: float = 180.0,
) -> dict:
    prompt = _PROMPT_QUALITY_ONLY.format(
        name=company_name or "unknown",
        text=page_text[:3000],
    )
    try:
        result = _call(prompt, ollama_url, model, timeout)
        return {
            "score": int(result["score"]) if result.get("score") is not None else None,
            "obsolete": result.get("obsolete"),
            "verdict": result.get("verdict"),
        }
    except Exception as exc:
        logger.warning("LLM unavailable: %s", exc)
        return {"score": None, "obsolete": None, "verdict": None}
