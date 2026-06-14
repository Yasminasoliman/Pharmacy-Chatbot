"""
support_node – handles all "contact pharmacy support" intents.

Responsibilities
----------------
1. Detect the support sub-intent (complaint / order inquiry / general question /
   medicine request / emergency) from the user message.
2. Create a structured support ticket and store it in state.
3. Compose a human-friendly acknowledgement that tells the user:
     - Their ticket ID
     - What will happen next (email / callback / live-chat)
     - Escalation path for emergencies
4. If SUPPORT_EMAIL is configured, actually send the ticket via SMTP.
5. If SUPPORT_API_URL is configured, POST the ticket to the pharmacy's
   support REST API.

Configuration (.env)
--------------------
SUPPORT_EMAIL=support@yourpharmacy.com      # SMTP destination
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=bot@yourpharmacy.com
SMTP_PASSWORD=your_app_password
SUPPORT_API_URL=https://api.yourpharmacy.com/support   # REST endpoint
PHARMACY_NAME=My Pharmacy                   # displayed in messages
PHARMACY_PHONE=+20-10-XXXX-XXXX
PHARMACY_WORKING_HOURS=Sat-Thu 9 AM – 10 PM
"""

from __future__ import annotations

import json
import logging
import os
import smtplib
import uuid
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, Optional

from state import PharmacyState

logger = logging.getLogger(__name__)

# ── env config ────────────────────────────────────────────────────────────── #
SUPPORT_EMAIL       = os.getenv("SUPPORT_EMAIL", "")
SMTP_HOST           = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT           = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER           = os.getenv("SMTP_USER", "")
SMTP_PASSWORD       = os.getenv("SMTP_PASSWORD", "")
SUPPORT_API_URL     = os.getenv("SUPPORT_API_URL", "")
PHARMACY_NAME       = os.getenv("PHARMACY_NAME", "Our Pharmacy")
PHARMACY_PHONE      = os.getenv("PHARMACY_PHONE", "N/A")
PHARMACY_WORKING_HOURS = os.getenv("PHARMACY_WORKING_HOURS", "Sat-Thu 9 AM – 10 PM")


# ── support sub-intent keywords ───────────────────────────────────────────── #
_EMERGENCY_KEYWORDS = [
    "emergency", "urgent", "dying", "overdose", "poison", "critical",
    "chest pain", "can't breathe", "unconscious",
]
_COMPLAINT_KEYWORDS = [
    "complaint", "complain", "wrong medicine", "expired", "bad service",
    "refund", "overcharged", "damaged", "problem with order",
]
_ORDER_KEYWORDS = [
    "order", "delivery", "track", "shipment", "where is my", "not arrived",
    "cancel order", "return",
]
_MEDICINE_REQUEST_KEYWORDS = [
    "don't have", "out of stock", "request medicine", "bring medicine",
    "can you order", "special order",
]


def _detect_sub_intent(message: str) -> str:
    msg = message.lower()
    if any(k in msg for k in _EMERGENCY_KEYWORDS):
        return "emergency"
    if any(k in msg for k in _COMPLAINT_KEYWORDS):
        return "complaint"
    if any(k in msg for k in _ORDER_KEYWORDS):
        return "order_inquiry"
    if any(k in msg for k in _MEDICINE_REQUEST_KEYWORDS):
        return "medicine_request"
    return "general_inquiry"


# ── ticket builder ────────────────────────────────────────────────────────── #

def _build_ticket(
    message: str,
    sub_intent: str,
    ocr_medicines: Optional[list] = None,
    availability: Optional[dict] = None,
) -> Dict[str, Any]:
    return {
        "ticket_id":    f"RX-{uuid.uuid4().hex[:8].upper()}",
        "created_at":   datetime.now(timezone.utc).isoformat(),
        "sub_intent":   sub_intent,
        "message":      message,
        "ocr_medicines": ocr_medicines or [],
        "availability_context": availability or {},
        "status":       "open",
        "channel":      "chatbot",
    }


# ── delivery methods ──────────────────────────────────────────────────────── #

def _send_email(ticket: Dict[str, Any]) -> bool:
    """Send ticket via SMTP. Returns True on success."""
    if not (SUPPORT_EMAIL and SMTP_USER and SMTP_PASSWORD):
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[{ticket['sub_intent'].upper()}] Support Ticket {ticket['ticket_id']}"
        msg["From"]    = SMTP_USER
        msg["To"]      = SUPPORT_EMAIL

        body = f"""\
New support ticket from PharmaAssist chatbot

Ticket ID  : {ticket['ticket_id']}
Type       : {ticket['sub_intent']}
Time       : {ticket['created_at']}
Status     : {ticket['status']}

--- User Message ---
{ticket['message']}

--- Context ---
Medicines discussed : {', '.join(ticket['ocr_medicines']) or 'none'}
Availability data   : {json.dumps(ticket['availability_context'], indent=2) if ticket['availability_context'] else 'none'}
"""
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, SUPPORT_EMAIL, msg.as_string())
        logger.info("Support ticket %s emailed to %s", ticket["ticket_id"], SUPPORT_EMAIL)
        return True
    except Exception as exc:
        logger.warning("Failed to send support email: %s", exc)
        return False


def _post_to_api(ticket: Dict[str, Any]) -> bool:
    """POST ticket to pharmacy support REST API. Returns True on success."""
    if not SUPPORT_API_URL:
        return False
    try:
        import httpx
        resp = httpx.post(
            f"{SUPPORT_API_URL}/tickets",
            json=ticket,
            timeout=8.0,
        )
        resp.raise_for_status()
        logger.info("Support ticket %s posted to API", ticket["ticket_id"])
        return True
    except Exception as exc:
        logger.warning("Failed to POST support ticket to API: %s", exc)
        return False


# ── response composer ─────────────────────────────────────────────────────── #

def _compose_response(ticket: Dict[str, Any], email_sent: bool, api_sent: bool) -> str:
    tid  = ticket["ticket_id"]
    kind = ticket["sub_intent"]

    # Emergency – always escalate immediately
    if kind == "emergency":
        return (
            f"🚨 **This sounds like an emergency.**\n\n"
            f"Please call emergency services or go to the nearest hospital immediately.\n\n"
            f"You can also reach our pharmacist directly:\n"
            f"📞 **{PHARMACY_PHONE}**\n\n"
            f"Your ticket **{tid}** has been flagged as urgent and will be reviewed immediately."
        )

    delivery_note = ""
    if email_sent:
        delivery_note = f"Your request has been emailed to our support team."
    elif api_sent:
        delivery_note = f"Your request has been submitted to our support system."
    else:
        delivery_note = (
            f"Our team will review your request during working hours "
            f"(**{PHARMACY_WORKING_HOURS}**)."
        )

    responses = {
        "complaint": (
            f"😔 We're sorry to hear about your experience.\n\n"
            f"Your complaint has been logged as ticket **{tid}**. "
            f"{delivery_note}\n\n"
            f"A team member will follow up with you within **24 hours**.\n\n"
            f"If you need immediate assistance:\n"
            f"📞 {PHARMACY_PHONE} | 🕐 {PHARMACY_WORKING_HOURS}"
        ),
        "order_inquiry": (
            f"📦 Got it — we'll look into your order.\n\n"
            f"Ticket **{tid}** has been created. {delivery_note}\n\n"
            f"Expected response time: **2–4 hours** during working hours.\n\n"
            f"📞 {PHARMACY_PHONE} | 🕐 {PHARMACY_WORKING_HOURS}"
        ),
        "medicine_request": (
            f"💊 We'll check if we can source that medicine for you.\n\n"
            f"Ticket **{tid}** has been logged. {delivery_note}\n\n"
            f"Our pharmacist will contact you within **1 business day** to confirm availability and pricing.\n\n"
            f"📞 {PHARMACY_PHONE} | 🕐 {PHARMACY_WORKING_HOURS}"
        ),
        "general_inquiry": (
            f"👋 Thanks for reaching out to {PHARMACY_NAME}!\n\n"
            f"Your inquiry has been logged as ticket **{tid}**. {delivery_note}\n\n"
            f"We aim to respond within **4–6 hours**.\n\n"
            f"📞 {PHARMACY_PHONE} | 🕐 {PHARMACY_WORKING_HOURS}"
        ),
    }

    return responses.get(kind, responses["general_inquiry"])


# ── LangGraph node ─────────────────────────────────────────────────────────── #

def support_node(state: PharmacyState) -> dict:
    """
    LangGraph node – handles support contact requests.

    Reads  : user_query, ocr_medicines, pharmacy_availability
    Writes : support_ticket, first_answer
    """
    message      = state.get("user_query", "")
    sub_intent   = _detect_sub_intent(message)
    ocr_meds     = state.get("ocr_medicines") or []
    availability = state.get("pharmacy_availability") or {}

    ticket     = _build_ticket(message, sub_intent, ocr_meds, availability)
    email_sent = _send_email(ticket)
    api_sent   = _post_to_api(ticket)

    # Log ticket to disk as fallback (always)
    _log_ticket(ticket)

    response = _compose_response(ticket, email_sent, api_sent)

    logger.info(
        "Support ticket %s created (type=%s, email=%s, api=%s)",
        ticket["ticket_id"], sub_intent, email_sent, api_sent,
    )

    return {
        "support_ticket": ticket,
        "first_answer":   response,
    }


def _log_ticket(ticket: Dict[str, Any]) -> None:
    """Persist ticket to support_tickets.jsonl as a fallback audit log."""
    from pathlib import Path
    log_dir = Path(__file__).parent.parent.parent / "support_tickets"
    log_dir.mkdir(exist_ok=True)
    with (log_dir / "tickets.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(ticket) + "\n")
