from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile

logger = logging.getLogger(__name__)

_CHROME_FLAGS = "--headless --no-sandbox --disable-dev-shm-usage --disable-gpu"

_SEO_AUDIT_IDS = [
    "meta-description", "document-title", "canonical", "robots-txt",
    "is-crawlable", "structured-data", "image-alt", "http-status-code",
    "font-size", "hreflang",
]

_PERF_METRIC_IDS = [
    "first-contentful-paint", "largest-contentful-paint",
    "total-blocking-time", "cumulative-layout-shift", "speed-index",
]


def run_lighthouse(url: str, timeout: float = 120.0) -> dict | None:
    if not shutil.which("lighthouse"):
        logger.warning(
            "lighthouse CLI not found in PATH — skipping audit "
            "(fix: npm install -g lighthouse and ensure Node is available)"
        )
        return None

    logger.info("Lighthouse audit starting for %s (timeout=%.0fs)", url, timeout)
    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp.close()
    try:
        proc = subprocess.run(
            [
                "lighthouse", url,
                "--output", "json",
                "--output-path", tmp.name,
                "--quiet",
                f"--chrome-flags={_CHROME_FLAGS}",
                "--only-categories=performance,accessibility,best-practices,seo",
                "--no-enable-error-reporting",
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if proc.returncode != 0:
            logger.warning(
                "Lighthouse subprocess failed for %s (exit %d) — stderr: %s — stdout: %s",
                url, proc.returncode, proc.stderr[:400], proc.stdout[:200],
            )
            return None
        with open(tmp.name, encoding="utf-8") as f:
            return json.load(f)
    except subprocess.TimeoutExpired:
        logger.warning("Lighthouse timed out after %.0fs for %s", timeout, url)
        return None
    except json.JSONDecodeError as exc:
        logger.warning("Lighthouse produced invalid JSON for %s: %s", url, exc)
        return None
    except OSError as exc:
        logger.warning("Lighthouse OSError for %s: %s", url, exc)
        return None
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def parse_lighthouse(lh: dict) -> dict:
    categories = lh.get("categories", {})
    audits = lh.get("audits", {})

    scores: dict[str, int | None] = {}
    for key, field in [
        ("performance", "performance"),
        ("accessibility", "accessibility"),
        ("best-practices", "best_practices"),
        ("seo", "seo"),
    ]:
        cat = categories.get(key, {})
        s = cat.get("score")
        scores[field] = round(s * 100) if s is not None else None

    seo: dict = {}
    for audit_id in _SEO_AUDIT_IDS:
        a = audits.get(audit_id, {})
        s = a.get("score")
        seo[audit_id.replace("-", "_")] = {
            "title": a.get("title", audit_id),
            "pass": (s == 1) if s is not None else None,
            "display_value": a.get("displayValue"),
        }

    metrics: dict = {}
    for audit_id in _PERF_METRIC_IDS:
        a = audits.get(audit_id, {})
        s = a.get("score")
        metrics[audit_id.replace("-", "_")] = {
            "display_value": a.get("displayValue"),
            "score": round(s * 100) if s is not None else None,
        }
    seo["metrics"] = metrics

    remarks: list[dict] = []
    for cat_key in ("performance", "accessibility", "best-practices", "seo"):
        for ref in (categories.get(cat_key) or {}).get("auditRefs", []):
            aid = ref.get("id")
            weight = ref.get("weight", 0)
            if not weight:
                continue
            a = audits.get(aid, {})
            s = a.get("score")
            if s is None or s == 1:
                continue
            remarks.append({
                "id": aid,
                "category": cat_key,
                "title": a.get("title", aid),
                "display_value": a.get("displayValue"),
                "score": round(s * 100),
                "weight": weight,
            })

    remarks.sort(key=lambda r: (-r["weight"], r["score"]))
    for r in remarks:
        del r["weight"]

    return {
        "scores": scores,
        "seo": seo,
        "remarks": remarks[:10],
    }
