# Pharmacy Chatbot – Upgrade Guide

## What was added

### ① Evaluation Layer (`app/evaluation/`)
Every response is automatically scored by an LLM judge on four dimensions:

| Dimension    | Meaning                                         | Pass threshold |
|--------------|-------------------------------------------------|----------------|
| relevance    | Does the answer address the query?              | ≥ 6 / 10       |
| safety       | No dangerous dosage / interaction advice?       | ≥ 6 / 10       |
| accuracy     | Consistent with tool data returned?             | ≥ 6 / 10       |
| completeness | Key tool data points covered?                   | ≥ 6 / 10       |

Results are appended to `eval_logs/eval_results.jsonl` after every response.

**New API endpoints:**
- `GET /eval/summary?n=100` – aggregated stats
- `GET /eval/recent?n=20`   – last N records

**LangSmith** (recommended): uncomment the three `LANGCHAIN_*` env vars and every
LangGraph run is automatically traced with token counts, latency per node, and
human-feedback support.

---

### ② OCR Prescription Agent (`app/nodes/ocr_node.py`)
Users can upload a prescription image. The pipeline:

1. Tries vision LLM (GPT-4o / Gemini) to parse medicine names as JSON
2. Falls back to Tesseract OCR if vision LLM is unavailable
3. Reformulates the query: *"Check availability for: Panadol, Augmentin"*
4. The rest of the graph runs normally

**New API endpoint:** `POST /chat/prescription` (multipart/form-data)

**Install Tesseract binary** (fallback):
```bash
# Ubuntu / Debian
sudo apt install tesseract-ocr

# macOS
brew install tesseract
```

---

### ③ Pharmacy Availability Agent (`app/nodes/pharmacy_agent_node.py`)
After `answer_node`, this node checks stock for every medicine found:

- If `PHARMACY_API_URL` is set → calls `GET <url>/stock?medicine=<name>`
- Otherwise → uses the built-in mock (realistic seed data for common Egyptian medicines)

The availability block is appended to the answer before `safety_node` processes it.

**To connect a real pharmacy API**, set `PHARMACY_API_URL` in `.env`.
Expected response contract:
```json
{ "in_stock": true, "quantity": 34, "price": 89.0, "note": "Prescription required" }
```

---

### ④ MCP Server (`app/mcp/server.py`)
Exposes all pharmacy tools via the Model Context Protocol.

**Run standalone:**
```bash
python app/mcp/server.py
```

**Connect to Claude Desktop:**  
Copy the block from `claude_desktop_config.json` into your Claude Desktop config,
replacing `<ABSOLUTE_PATH_TO_PROJECT>` with the real path.

**Tools exposed:**
- `medicine_lookup` – brand name → price, manufacturer, prescription status
- `disease_lookup`  – disease → list of medicines
- `generic_name_lookup` – active ingredient → brands
- `drug_information` – mechanism, side effects, contraindications
- `check_pharmacy_stock` – real-time stock status

---

## Updated graph flow

```
[text]──────────────────────────────────────────┐
                                                  ▼
[image] ──► ocr_node ──► intent_node ──► router
                               │
            answer_directly ◄──┤──► need_search ──► search_node ──► tool_node
                               │                         │
                               │                    answer_node
                               │                         │
                               │                pharmacy_agent_node  ← NEW
                               │                         │
                               └──────────────► safety_node
                                                         │
                                                     eval_node       ← NEW
                                                         │
                                                        END
```

---

## Quickstart

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Install Tesseract (optional, OCR fallback)
sudo apt install tesseract-ocr   # or: brew install tesseract

# 3. Copy and fill env vars
cp .env.example .env

# 4. Start the backend
cd app && python main.py

# 5. Start the frontend (new tab)
streamlit run frontend/app.py
```
