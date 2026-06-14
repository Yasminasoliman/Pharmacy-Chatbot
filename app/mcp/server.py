"""
MCP server for the Pharmacy Chatbot.

Exposes four tools via the Model Context Protocol so external agents
(Claude Desktop, other MCP clients) can call them directly.

Run standalone:
    python app/mcp/server.py

Or register in claude_desktop_config.json:
    {
      "mcpServers": {
        "pharmacy": {
          "command": "python",
          "args": ["<absolute-path>/app/mcp/server.py"]
        }
      }
    }

Dependencies:
    pip install mcp
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys

# Ensure app/ is on the path when this file is run directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────── #
# Tool schemas                                                                 #
# ──────────────────────────────────────────────────────────────────────────── #

TOOL_SCHEMAS = [
    {
        "name": "medicine_lookup",
        "description": (
            "Look up a specific medicine by brand name. "
            "Returns price, manufacturer, prescription requirement, generic name, and disease."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "medicine_name": {
                    "type": "string",
                    "description": "Brand or common name of the medicine (e.g. 'Panadol', 'Augmentin')",
                }
            },
            "required": ["medicine_name"],
        },
    },
    {
        "name": "disease_lookup",
        "description": (
            "Find medicines used to treat a specific disease or condition. "
            "Returns up to 10 matching medicines with prices and prescription info."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "disease_name": {
                    "type": "string",
                    "description": "Disease or medical condition (e.g. 'diabetes', 'hypertension', 'acne')",
                }
            },
            "required": ["disease_name"],
        },
    },
    {
        "name": "generic_name_lookup",
        "description": (
            "Search medicines by active ingredient / generic name. "
            "Useful for finding brand alternatives for a molecule."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "generic_name": {
                    "type": "string",
                    "description": "Active ingredient / generic name (e.g. 'paracetamol', 'ibuprofen')",
                }
            },
            "required": ["generic_name"],
        },
    },
    {
        "name": "drug_information",
        "description": (
            "Retrieve detailed drug information: mechanism of action, indications, "
            "side effects, dosage, contraindications, and interactions."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "drug_name": {
                    "type": "string",
                    "description": "Medicine or drug name",
                }
            },
            "required": ["drug_name"],
        },
    },
    {
        "name": "check_pharmacy_stock",
        "description": (
            "Check real-time stock availability of a medicine at the pharmacy. "
            "Returns in_stock status, quantity, price, and notes."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "medicine_name": {
                    "type": "string",
                    "description": "Medicine name to check in the pharmacy",
                }
            },
            "required": ["medicine_name"],
        },
    },
]


# ──────────────────────────────────────────────────────────────────────────── #
# Tool dispatcher                                                              #
# ──────────────────────────────────────────────────────────────────────────── #

def _dispatch(tool_name: str, arguments: dict) -> str:
    """
    Call the appropriate LangChain tool and return the string result.
    Importing here (lazily) avoids DB connection at import time.
    """
    from tools import medicine_lookup, disease_lookup, generic_name_lookup, drug_information  # noqa
    from nodes.pharmacy_agent_node import _mock_api, _http_check, PHARMACY_API_URL  # noqa

    dispatch_map = {
        "medicine_lookup":    lambda: medicine_lookup.invoke(arguments),
        "disease_lookup":     lambda: disease_lookup.invoke(arguments),
        "generic_name_lookup": lambda: generic_name_lookup.invoke(arguments),
        "drug_information":   lambda: drug_information.invoke(arguments),
        "check_pharmacy_stock": lambda: json.dumps(
            _http_check(arguments["medicine_name"])
            if PHARMACY_API_URL
            else _mock_api.check(arguments["medicine_name"])
        ),
    }

    handler = dispatch_map.get(tool_name)
    if handler is None:
        raise ValueError(f"Unknown tool: {tool_name}")
    return handler()


# ──────────────────────────────────────────────────────────────────────────── #
# MCP server setup                                                             #
# ──────────────────────────────────────────────────────────────────────────── #

async def main() -> None:
    try:
        from mcp.server import Server
        from mcp.server.stdio import stdio_server
        from mcp.types import Tool, TextContent
    except ImportError:
        print(
            "mcp package not installed. Run: pip install mcp",
            file=sys.stderr,
        )
        sys.exit(1)

    server = Server("pharmacy-chatbot")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name=t["name"],
                description=t["description"],
                inputSchema=t["inputSchema"],
            )
            for t in TOOL_SCHEMAS
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        try:
            result = _dispatch(name, arguments)
        except Exception as exc:
            result = json.dumps({"error": str(exc)})
        return [TextContent(type="text", text=result)]

    async with stdio_server(server) as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
