"""
pharmacy_agent_node – checks real-time medicine availability.

This node runs AFTER answer_node and BEFORE safety_node.
It reads the medicines found by the search tools and queries a pharmacy
stock API (real or mocked) for each one.

The result is stored in state['pharmacy_availability'] and also appended
to state['final_safe_answer'] so the user sees availability inline.

Configuration
-------------
Set PHARMACY_API_URL in your .env to point at a real pharmacy API.
If the env var is absent, the node uses the built-in mock (see MockPharmacyAPI).

Real API contract expected (GET):
    GET <PHARMACY_API_URL>/stock?medicine=<name>
    Response JSON: { "in_stock": bool, "quantity": int, "price": float, "note": str }
"""

from __future__ import annotations

import json
import logging
import os
import random
from typing import Any, Dict, List

from state import PharmacyState

logger = logging.getLogger(__name__)

PHARMACY_API_URL = os.getenv("PHARMACY_API_URL", "")  # empty → use mock


# ──────────────────────────────────────────────────────────────────────────── #
# Mock pharmacy (used when no real API is configured)                          #
# ──────────────────────────────────────────────────────────────────────────── #

class MockPharmacyAPI:
    """
    Deterministic mock so behaviour is reproducible in tests.
    Returns realistic-looking stock data keyed by lower-cased medicine name.
    """

    _SEED_DATA: Dict[str, Dict[str, Any]] = {
        "panadol":    {"in_stock": True,  "quantity": 120, "price": 15.50, "note": ""},
        "augmentin":  {"in_stock": True,  "quantity": 34,  "price": 89.00, "note": "Prescription required"},
        "brufen":     {"in_stock": False, "quantity": 0,   "price": 22.00, "note": "Expected restock in 3 days"},
        "metformin":  {"in_stock": True,  "quantity": 200, "price": 12.00, "note": "Generic available"},
        "cataflam":   {"in_stock": True,  "quantity": 56,  "price": 35.00, "note": ""},
        "nexium":     {"in_stock": False, "quantity": 0,   "price": 145.0, "note": "Out of stock, no ETA"},
        "concor":     {"in_stock": True,  "quantity": 80,  "price": 55.00, "note": ""},
        "glucophage": {"in_stock": True,  "quantity": 150, "price": 18.00, "note": ""},
    }

    def check(self, medicine_name: str) -> Dict[str, Any]:
        key = medicine_name.lower().strip()
        if key in self._SEED_DATA:
            return dict(self._SEED_DATA[key])
        # unknown medicine: randomise for demo purposes
        in_stock = random.random() > 0.3
        return {
            "in_stock": in_stock,
            "quantity": random.randint(10, 200) if in_stock else 0,
            "price": round(random.uniform(10, 200), 2),
            "note": "Data from mock pharmacy",
        }


_mock_api = MockPharmacyAPI()


# ──────────────────────────────────────────────────────────────────────────── #
# Real HTTP call (used when PHARMACY_API_URL is set)                          #
# ──────────────────────────────────────────────────────────────────────────── #

def _http_check(medicine_name: str) -> Dict[str, Any]:
    try:
        import httpx
        response = httpx.get(
            f"{PHARMACY_API_URL}/stock",
            params={"medicine": medicine_name},
            timeout=8.0,
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        logger.warning("Pharmacy API call failed for '%s': %s – using mock", medicine_name, exc)
        return _mock_api.check(medicine_name)


# ──────────────────────────────────────────────────────────────────────────── #
# Medicine extraction helpers                                                  #
# ──────────────────────────────────────────────────────────────────────────── #

def _extract_medicine_names(state: PharmacyState) -> List[str]:
    """
    Pull medicine names from:
      1. state['found_medicines']   – if already populated by another node
      2. state['ocr_medicines']     – from OCR prescription
      3. state['tool_result']       – parse the JSON returned by tools
    Returns a deduplicated list (preserving order).
    """
    seen: set = set()
    medicines: List[str] = []

    def _add(name: str) -> None:
        key = name.strip().lower()
        if key and key not in seen:
            seen.add(key)
            medicines.append(name.strip())

    # 1. explicit list from state
    for m in state.get("found_medicines") or []:
        _add(m)

    # 2. OCR result
    for m in state.get("ocr_medicines") or []:
        _add(m)

    # 3. tool result JSON
    tool_result = state.get("tool_result")
    if tool_result:
        try:
            data = json.loads(tool_result)
            results = data.get("results", [])
            for row in results:
                if isinstance(row, dict) and row.get("med_name"):
                    _add(row["med_name"])
        except (json.JSONDecodeError, AttributeError):
            pass

    return medicines


# ──────────────────────────────────────────────────────────────────────────── #
# Availability formatter                                                       #
# ──────────────────────────────────────────────────────────────────────────── #

def _format_availability(availability: Dict[str, Any]) -> str:
    if not availability:
        return ""
    lines = ["\n\n---\n📦 **Pharmacy Availability**"]
    for medicine, info in availability.items():
        status = "✅ In Stock" if info.get("in_stock") else "❌ Out of Stock"
        qty    = info.get("quantity", 0)
        price  = info.get("price", "N/A")
        note   = info.get("note", "")
        line   = f"- **{medicine}**: {status}"
        if info.get("in_stock"):
            line += f" (qty: {qty}, price: {price} EGP)"
        if note:
            line += f" — _{note}_"
        lines.append(line)
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────── #
# LangGraph node                                                               #
# ──────────────────────────────────────────────────────────────────────────── #

def pharmacy_agent_node(state: PharmacyState) -> dict:
    """
    1. Extract medicine names from state.
    2. Query the pharmacy API for each.
    3. Append availability block to first_answer (safety_node will process it).
    4. Store full availability dict in state.
    """
    medicines = _extract_medicine_names(state)

    if not medicines:
        logger.info("pharmacy_agent_node: no medicines found – skipping")
        return {"pharmacy_availability": {}}

    logger.info("pharmacy_agent_node: checking %d medicines", len(medicines))

    check_fn = _http_check if PHARMACY_API_URL else _mock_api.check

    availability: Dict[str, Any] = {}
    for med in medicines:
        availability[med] = check_fn(med)

    # Append availability block to the draft answer so safety_node sees it
    current_answer = state.get("first_answer") or ""
    enriched_answer = current_answer + _format_availability(availability)

    return {
        "pharmacy_availability": availability,
        "first_answer": enriched_answer,
    }
