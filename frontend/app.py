"""
Streamlit frontend – v2.1
Tabs:
  💬  Chat              – text chat (all intents)
  📋  Prescription      – upload image → OCR → availability
  🎧  Support           – contact pharmacy / view my tickets
  📊  Eval Dashboard    – live evaluation scores
"""

import json
import time
import requests
import streamlit as st

API_BASE = "http://localhost:8000"

st.set_page_config(page_title="PharmaAssist", page_icon="💊", layout="wide")

# ── session init ──────────────────────────────────────────────────────────── #
for key, default in [
    ("chat_history", []),
    ("eval_history", []),
    ("my_tickets",   []),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ── helpers ───────────────────────────────────────────────────────────────── #

def _stream(endpoint: str, payload=None, files=None, data=None):
    """Generic SSE consumer. Yields parsed event dicts."""
    try:
        if files:
            resp = requests.post(f"{API_BASE}{endpoint}", files=files, data=data,
                                 stream=True, timeout=90)
        else:
            resp = requests.post(f"{API_BASE}{endpoint}", json=payload,
                                 stream=True, timeout=300)
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line:
                continue
            text = line.decode() if isinstance(line, bytes) else line
            if text.startswith("data: "):
                raw = text[6:]
                if raw == "[DONE]":
                    return
                try:
                    yield json.loads(raw)
                except json.JSONDecodeError:
                    pass
    except requests.RequestException as exc:
        yield {"type": "error", "message": str(exc)}


def score_color(v):
    if v is None or v == -1:
        return "gray"
    return "green" if v >= 8 else ("orange" if v >= 6 else "red")


def render_eval_badge(scores: dict):
    if not scores:
        return
    with st.expander("🔍 Evaluation Scores", expanded=False):
        cols = st.columns(4)
        for col, (label, key) in zip(cols, [
            ("Relevance", "relevance"), ("Safety", "safety"),
            ("Accuracy", "accuracy"), ("Completeness", "completeness"),
        ]):
            v = scores.get(key)
            col.metric(label, "N/A" if v in (None, -1) else f"{v}/10")
        issues = scores.get("issues", [])
        if issues:
            st.warning("⚠️ " + " | ".join(issues))
        st.success("✅ Passed" if scores.get("passed") else "❌ Below threshold")


def render_ticket_card(ticket: dict):
    kind_icon = {
        "emergency":       "🚨",
        "complaint":       "😔",
        "order_inquiry":   "📦",
        "medicine_request": "💊",
        "general_inquiry": "👋",
    }.get(ticket.get("sub_intent", ""), "📋")
    with st.container(border=True):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(
                f"{kind_icon} **{ticket.get('sub_intent', 'inquiry').replace('_', ' ').title()}** "
                f"— Ticket `{ticket.get('ticket_id')}`"
            )
            st.caption(f"🕐 {ticket.get('created_at', '')[:19].replace('T', ' ')} UTC")
        with col2:
            status = ticket.get("status", "open")
            st.markdown(
                f"<span style='background:#2e7d32;color:white;padding:2px 10px;border-radius:10px;font-size:0.8rem'>{status}</span>"
                if status == "open" else
                f"<span style='background:#555;color:white;padding:2px 10px;border-radius:10px;font-size:0.8rem'>{status}</span>",
                unsafe_allow_html=True,
            )
        st.caption(f"Message: {ticket.get('message', '')[:120]}")
        meds = ticket.get("ocr_medicines", [])
        if meds:
            st.caption(f"Medicines: {', '.join(meds)}")


# ══════════════════════════════════════════════════════════════════════════════ #
tab_chat, tab_rx, tab_support, tab_eval = st.tabs(
    ["💬 Chat", "📋 Prescription Upload", "🎧 Contact Support", "📊 Eval Dashboard"]
)


# ══════════════════════════════════════════════════════════════════════════════ #
# TAB 1 – CHAT                                                                 #
# ══════════════════════════════════════════════════════════════════════════════ #
with tab_chat:
    for entry in st.session_state.chat_history:
        with st.chat_message(entry["role"]):
            st.markdown(entry["content"])
            if entry["role"] == "assistant":
                if entry.get("ticket"):
                    render_ticket_card(entry["ticket"])
                if entry.get("eval_scores"):
                    render_eval_badge(entry["eval_scores"])

    if prompt := st.chat_input("Ask about medicines, diseases, or type 'contact support'…"):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            placeholder  = st.empty()
            full_resp    = ""
            eval_scores  = None
            ticket       = None
            availability = None

            for ev in _stream("/chat/stream", {"message": prompt, "history": st.session_state.chat_history[:-1]}):
                t = ev.get("type")
                if t == "token":
                    full_resp += ev.get("content", "")
                    placeholder.markdown(full_resp + "▌")
                elif t == "final_answer":
                    full_resp = ev.get("content", "")
                    placeholder.markdown(full_resp)
                elif t == "availability":
                    availability = ev.get("data", {})
                elif t == "support_ticket":
                    ticket = ev.get("ticket")
                    if ticket:
                        st.session_state.my_tickets.append(ticket)
                elif t == "eval_scores":
                    eval_scores = ev.get("scores")
                elif t == "error":
                    st.error(ev.get("message"))

            placeholder.markdown(full_resp)

            if availability:
                with st.expander("📦 Pharmacy Availability", expanded=True):
                    for med, info in availability.items():
                        icon = "✅" if info.get("in_stock") else "❌"
                        st.write(f"**{med}**: {icon} Qty: {info.get('quantity',0)} | Price: {info.get('price','N/A')} EGP")
                        if info.get("note"):
                            st.caption(info["note"])

            if ticket:
                render_ticket_card(ticket)

            if eval_scores:
                render_eval_badge(eval_scores)

        st.session_state.chat_history.append({
            "role": "assistant", "content": full_resp,
            "ticket": ticket, "eval_scores": eval_scores,
        })


# ══════════════════════════════════════════════════════════════════════════════ #
# TAB 2 – PRESCRIPTION UPLOAD                                                  #
# ══════════════════════════════════════════════════════════════════════════════ #
with tab_rx:
    st.subheader("📋 Upload a Prescription")
    st.caption("Upload a photo or scan — medicines are extracted automatically and checked for availability.")

    uploaded = st.file_uploader("Image or PDF", type=["jpg","jpeg","png","pdf"], key="rx_upload")
    note     = st.text_input("Optional note", key="rx_note")

    if uploaded and st.button("🔍 Analyse Prescription", type="primary"):
        file_bytes = uploaded.read()
        if uploaded.type.startswith("image"):
            st.image(file_bytes, caption="Uploaded prescription", width=380)
        st.divider()
        col_ocr, col_resp = st.columns([1, 2])
        with col_ocr:
            st.subheader("🔬 Extracted Medicines")
            ocr_ph = st.empty(); ocr_ph.info("Extracting…")
        with col_resp:
            st.subheader("💬 Response")
            resp_ph  = st.empty()
            avail_ph = st.empty()
            eval_ph  = st.empty()

        full_resp = ""; ocr_meds = []; availability = None; eval_scores = None; ticket = None

        for ev in _stream("/chat/prescription",
                          files={"file": (uploaded.name, file_bytes, "image/jpeg")},
                          data={"message": note, "history": json.dumps(st.session_state.chat_history)}):
            t = ev.get("type")
            if t == "ocr_result":
                ocr_meds = ev.get("medicines", [])
                ocr_ph.success("**Found:**\n" + "\n".join(f"- {m}" for m in ocr_meds))
            elif t == "token":
                full_resp += ev.get("content", "")
                resp_ph.markdown(full_resp + "▌")
            elif t == "final_answer":
                full_resp = ev.get("content", "")
                resp_ph.markdown(full_resp)
            elif t == "availability":
                availability = ev.get("data", {})
                avail_ph.info("\n\n".join(
                    f"**{m}**: {'✅' if i.get('in_stock') else '❌'} | Qty: {i.get('quantity',0)} | Price: {i.get('price','N/A')} EGP"
                    for m, i in availability.items()
                ))
            elif t == "support_ticket":
                ticket = ev.get("ticket")
                if ticket:
                    st.session_state.my_tickets.append(ticket)
            elif t == "eval_scores":
                eval_scores = ev.get("scores")
            elif t == "error":
                resp_ph.error(ev.get("message"))

        resp_ph.markdown(full_resp)
        if not ocr_meds:
            ocr_ph.warning("Could not extract medicines. Please try a clearer image.")
        if eval_scores:
            with eval_ph.container():
                render_eval_badge(eval_scores)


# ══════════════════════════════════════════════════════════════════════════════ #
# TAB 3 – CONTACT SUPPORT                                                      #
# ══════════════════════════════════════════════════════════════════════════════ #
with tab_support:
    st.subheader("🎧 Contact Pharmacy Support")

    col_form, col_tickets = st.columns([1, 1])

    with col_form:
        st.markdown("**Send a message to our support team**")
        st.caption("Describe your issue and we'll create a ticket and notify the team.")

        support_type = st.selectbox("Issue type", [
            "General inquiry",
            "Complaint",
            "Order / Delivery inquiry",
            "Medicine request (out of stock)",
            "Emergency",
        ], key="support_type")

        support_msg = st.text_area(
            "Your message",
            placeholder="e.g. I received the wrong medicine in my order…",
            height=140,
            key="support_msg",
        )

        if st.button("📩 Submit to Support", type="primary", key="support_submit"):
            if not support_msg.strip():
                st.warning("Please enter a message.")
            else:
                # Prepend the category so intent detection is reliable
                full_message = f"[{support_type}] {support_msg}"

                with st.spinner("Submitting your request…"):
                    ticket       = None
                    full_resp    = ""
                    for ev in _stream("/chat/stream", {"message": full_message, "history": []}):
                        t = ev.get("type")
                        if t == "token":
                            full_resp += ev.get("content", "")
                        elif t == "final_answer":
                            full_resp = ev.get("content", "")
                        elif t == "support_ticket":
                            ticket = ev.get("ticket")
                            if ticket:
                                st.session_state.my_tickets.append(ticket)
                        elif t == "error":
                            st.error(ev.get("message"))

                st.success("✅ Request submitted!")
                st.markdown(full_resp)
                if ticket:
                    render_ticket_card(ticket)

    with col_tickets:
        st.markdown("**My Tickets (this session)**")

        # also try fetching from backend
        try:
            server_tickets = requests.get(f"{API_BASE}/support/tickets?limit=20", timeout=4).json()
        except Exception:
            server_tickets = []

        all_tickets = server_tickets or st.session_state.my_tickets

        if not all_tickets:
            st.info("No tickets yet. Submit a request on the left.")
        else:
            for t in all_tickets[:10]:
                render_ticket_card(t)
                st.write("")

    st.divider()
    st.subheader("📞 Direct Contact")
    info_col1, info_col2 = st.columns(2)
    with info_col1:
        st.markdown("**Phone / WhatsApp**")
        st.markdown("`+20-10-XXXX-XXXX`")
        st.markdown("**Working Hours**")
        st.markdown("Sat–Thu: 9 AM – 10 PM")
    with info_col2:
        st.markdown("**Email**")
        st.markdown("`support@yourpharmacy.com`")
        st.markdown("**Response time**")
        st.markdown("< 4 hours during working hours")


# ══════════════════════════════════════════════════════════════════════════════ #
# TAB 4 – EVAL DASHBOARD                                                       #
# ══════════════════════════════════════════════════════════════════════════════ #
with tab_eval:
    st.subheader("📊 Evaluation Dashboard")
    n_records = st.slider("Records to analyse", 10, 500, 100, key="eval_n")

    try:
        summary = requests.get(f"{API_BASE}/eval/summary", params={"n": n_records}, timeout=5).json()
    except Exception:
        summary = {}
    try:
        recent = requests.get(f"{API_BASE}/eval/recent", params={"n": 20}, timeout=5).json()
    except Exception:
        recent = []

    if not summary or "message" in summary:
        st.info("No evaluation data yet. Send some messages first.")
    else:
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Total Evaluated",  summary.get("total_evaluated", 0))
        k2.metric("Pass Rate",        f"{summary.get('pass_rate', 0)}%")
        k3.metric("Avg Relevance",    summary.get("avg_relevance", "N/A"))
        k4.metric("Avg Safety",       summary.get("avg_safety", "N/A"))
        k5.metric("Avg Latency",      f"{summary.get('avg_latency_ms', 0)} ms")
        st.divider()

        st.subheader("Average Scores")
        for label, key in [("Relevance","avg_relevance"),("Safety","avg_safety"),
                            ("Accuracy","avg_accuracy"),("Completeness","avg_completeness")]:
            v = summary.get(key)
            if v and v != -1:
                st.write(f"**{label}**: {v}/10")
                st.progress(int(v * 10))

        issues = summary.get("common_issues", [])
        if issues:
            st.subheader("⚠️ Most Common Issues")
            for i in issues:
                st.markdown(f"- {i}")

        if recent:
            st.divider()
            st.subheader("Recent Evaluations")
            import pandas as pd
            df = pd.DataFrame(recent)[
                ["timestamp","query","relevance","safety","accuracy","completeness","passed","latency_ms"]
            ]
            df["query"]     = df["query"].str[:60] + "…"
            df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.strftime("%H:%M:%S")
            st.dataframe(df, use_container_width=True, hide_index=True)
