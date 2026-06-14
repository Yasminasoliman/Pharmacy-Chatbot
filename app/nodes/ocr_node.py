"""
ocr_node – extracts medicine names from an uploaded prescription image.

Strategy (two-tier):
  1. Primary  : send the image to the configured LLM if it supports vision
                (OpenAI gpt-4o / gemini-1.5-pro / grok-vision etc.)
  2. Fallback : Tesseract OCR (pytesseract) – works offline, no API cost.

The node writes three fields to state:
  ocr_text      – raw text extracted from the image
  ocr_medicines – list of medicine names parsed from the text
  user_query    – overwritten with "Check availability for: <names>"
                  so the rest of the graph handles it normally
"""

from __future__ import annotations

import base64
import io
import json
import logging
import re
from typing import List

from langchain_core.messages import HumanMessage, SystemMessage

from state import PharmacyState


# NEW
from config import VISION_LLM as LLM
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────── #
# Helpers                                                                      #
# ──────────────────────────────────────────────────────────────────────────── #

def _b64_to_pil(b64_str: str):
    """Decode a base64 image string to a PIL Image."""
    from PIL import Image  # lazy import – only needed for fallback path
    raw = base64.b64decode(b64_str)
    return Image.open(io.BytesIO(raw))


def _tesseract_extract(b64_str: str) -> str:
    """Extract text with Tesseract (fallback)."""
    try:
        import pytesseract
        img = _b64_to_pil(b64_str)
        return pytesseract.image_to_string(img)
    except ImportError:
        logger.warning(
            "pytesseract not installed. "
            "Run: pip install pytesseract pillow  (and install Tesseract binary)"
        )
        return ""
    except Exception as exc:
        logger.warning("Tesseract failed: %s", exc)
        return ""


def _llm_vision_extract(b64_str: str) -> str:
    """
    Send the image to the LLM using vision capabilities.
    Returns raw extracted text.  Falls back to empty string on error.
    """
    # OLD

    try:
        from config import VISION_LLM as LLM  # noqa: PLC0415
        response = LLM.invoke([
            SystemMessage(
                content=(
                    "You are a prescription OCR assistant. "
                    "Extract every medicine / drug name from the image. "
                    "Return ONLY a JSON array of strings, e.g. [\"Panadol\",\"Augmentin\"]. "
                    "No other text."
                )
            ),
            HumanMessage(
                content=[
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{b64_str}",
                            "detail": "high",
                        },
                    },
                    {
                        "type": "text",
                        "text": "List all medicine names from this prescription.",
                    },
                ]
            ),
        ])
        return response.content
    except Exception as exc:
        logger.warning("LLM vision extraction failed (%s) – falling back to Tesseract", exc)
        return ""


def _parse_medicine_names(raw_text: str) -> List[str]:
    """
    Try to parse a JSON array from raw_text.
    If that fails, split by newlines / commas and clean up.
    """
    raw_text = raw_text.strip()

    # strip optional ``` fences
    if raw_text.startswith("```"):
        raw_text = re.sub(r"^```[a-z]*\n?", "", raw_text)
        raw_text = raw_text.rstrip("`").strip()

    # attempt JSON parse
    try:
        result = json.loads(raw_text)
        if isinstance(result, list):
            return [str(m).strip() for m in result if str(m).strip()]
    except json.JSONDecodeError:
        pass

    # fallback: split by newline / comma / semicolon
    parts = re.split(r"[\n,;]+", raw_text)
    medicines = []
    for part in parts:
        clean = re.sub(r"^\d+[\.\)]\s*", "", part).strip()
        if clean and len(clean) > 1:
            medicines.append(clean)
    return medicines


# ──────────────────────────────────────────────────────────────────────────── #
# LangGraph node                                                               #
# ──────────────────────────────────────────────────────────────────────────── #

def ocr_node(state: PharmacyState) -> dict:
    """
    Reads state['prescription_image'] (base64 string).
    Writes:
        ocr_text       – raw extracted text
        ocr_medicines  – list of medicine names
        user_query     – reformulated query for the search pipeline
    """
    b64_image = state.get("prescription_image", "")
    if not b64_image:
        logger.warning("ocr_node called but prescription_image is empty")
        return {
            "ocr_text": "",
            "ocr_medicines": [],
            "user_query": state.get("user_query", ""),
        }

    # ── 1. Try vision LLM first ──────────────────────────────────────────── #
    raw_text = _llm_vision_extract(b64_image)

    # If LLM returned a JSON array we can parse directly
    medicines = _parse_medicine_names(raw_text)

    # ── 2. Fallback to Tesseract if LLM gave nothing useful ─────────────── #
    if not medicines:
        logger.info("LLM vision returned no medicines – running Tesseract")
        raw_text = _tesseract_extract(b64_image)
        medicines = _parse_medicine_names(raw_text)

    if medicines:
        new_query = (
            f"Check availability and provide information for these medicines "
            f"from a prescription: {', '.join(medicines)}"
        )
    else:
        new_query = (
            "I uploaded a prescription but the medicines could not be read clearly. "
            "Please ask the user to upload a clearer image or type the medicine names."
        )

    logger.info("OCR extracted %d medicine(s): %s", len(medicines), medicines)

    return {
        "ocr_text": raw_text,
        "ocr_medicines": medicines,
        "user_query": new_query,
    }
