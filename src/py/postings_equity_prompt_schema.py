#!/usr/bin/env python3
"""Shared prompt and schema helpers for the active postings-equity pipeline."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

from src.py.project_paths import RESULTS_RAW


DEFAULT_MODEL = "gpt-5-nano"


def default_candidates_parquet() -> Path:
    return RESULTS_RAW / "postings_description_equity" / "equity_candidates.parquet"


def system_prompt() -> str:
    return (
        "You are an information extraction engine.\n"
        "Extract equity-compensation-related information from a job posting.\n"
        "\n"
        "Rules:\n"
        "- Output must be valid JSON matching the provided schema (no markdown).\n"
        "- Do not hallucinate. Only extract details explicitly supported by the text.\n"
        "- If a field is unknown or not stated, use null (or false for booleans).\n"
        "- Treat 'equity instruments' as offered compensation/benefits to the employee, not job duties.\n"
        "- Keep evidence quotes short and directly copied from the text.\n"
        "- Evidence quotes must justify the key decisions (context + offered/not offered + instruments).\n"
        "- You may use the EQUITY_KEYWORD_SNIPPETS section to find relevant lines quickly.\n"
    )


def user_prompt_template() -> str:
    return (
        "Job posting:\n"
        "job_id: {job_id}\n"
        "company_cleaned: {company_cleaned}\n"
        "post_date: {post_date}\n"
        "title: {title}\n"
        "\n"
        "EQUITY_KEYWORD_SNIPPETS (auto-extracted, may be empty):\n"
        "{keyword_snippets}\n"
        "\n"
        "DESCRIPTION:\n"
        "{description}\n"
    )


def json_schema() -> Dict[str, Any]:
    instrument_obj = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "mentioned": {"type": "boolean"},
            "details_text": {"type": ["string", "null"]},
        },
        "required": ["mentioned", "details_text"],
    }

    return {
        "name": "equity_comp_extraction",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "job_id": {"type": "string"},
                "equity_context": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": [
                            "employee_equity_compensation",
                            "private_equity_investing",
                            "dei_or_pay_equity",
                            "home_equity_lending",
                            "other",
                        ],
                    },
                },
                "employee_equity_comp_offered": {"type": "boolean"},
                "equity_instruments": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "stock_options": instrument_obj,
                        "rsu": instrument_obj,
                        "restricted_stock": instrument_obj,
                        "espp": instrument_obj,
                        "esop": instrument_obj,
                        "phantom_equity": instrument_obj,
                        "profit_interest": instrument_obj,
                        "carried_interest": instrument_obj,
                        "stock_appreciation_rights": instrument_obj,
                        "other_equity": instrument_obj,
                    },
                    "required": [
                        "stock_options",
                        "rsu",
                        "restricted_stock",
                        "espp",
                        "esop",
                        "phantom_equity",
                        "profit_interest",
                        "carried_interest",
                        "stock_appreciation_rights",
                        "other_equity",
                    ],
                },
                "vesting": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "mentioned": {"type": "boolean"},
                        "cliff_months": {"type": ["integer", "null"]},
                        "duration_months": {"type": ["integer", "null"]},
                        "schedule_text": {"type": ["string", "null"]},
                    },
                    "required": ["mentioned", "cliff_months", "duration_months", "schedule_text"],
                },
                "pricing_or_valuation": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "mentions_409a": {"type": "boolean"},
                        "mentions_strike_or_exercise_price": {"type": "boolean"},
                        "strike_or_exercise_price_amount": {"type": ["number", "null"]},
                        "strike_or_exercise_price_currency": {"type": ["string", "null"]},
                    },
                    "required": [
                        "mentions_409a",
                        "mentions_strike_or_exercise_price",
                        "strike_or_exercise_price_amount",
                        "strike_or_exercise_price_currency",
                    ],
                },
                "equity_amounts": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "mentions_shares": {"type": "boolean"},
                        "shares": {"type": ["number", "null"]},
                        "mentions_percent_ownership": {"type": "boolean"},
                        "percent_ownership": {"type": ["number", "null"]},
                        "mentions_dollar_value": {"type": "boolean"},
                        "dollar_value": {"type": ["number", "null"]},
                        "dollar_value_currency": {"type": ["string", "null"]},
                    },
                    "required": [
                        "mentions_shares",
                        "shares",
                        "mentions_percent_ownership",
                        "percent_ownership",
                        "mentions_dollar_value",
                        "dollar_value",
                        "dollar_value_currency",
                    ],
                },
                "evidence_quotes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 3,
                },
                "notes": {"type": ["string", "null"]},
            },
            "required": [
                "job_id",
                "equity_context",
                "employee_equity_comp_offered",
                "equity_instruments",
                "vesting",
                "pricing_or_valuation",
                "equity_amounts",
                "evidence_quotes",
                "notes",
            ],
        },
    }


def extract_keyword_snippets(*, title: str, description: str) -> List[str]:
    """Pull short windows around equity-related terms for prompt context."""
    text = f"{title}\n{description}".strip()
    low = text.lower()

    tokens = [
        "restricted stock unit",
        "restricted stock",
        "rsu",
        "stock option",
        "option grant",
        "equity compensation",
        "equity grant",
        "equity",
        "espp",
        "employee stock purchase",
        "esop",
        "employee stock ownership",
        "phantom equity",
        "phantom stock",
        "profit interest",
        "carried interest",
        "stock appreciation right",
        "409a",
        "cap table",
        "capitalization table",
        "strike price",
        "exercise price",
    ]
    tokens.sort(key=len, reverse=True)

    snippets: List[str] = []
    seen: set[str] = set()
    for token in tokens:
        idx = 0
        while True:
            hit = low.find(token, idx)
            if hit < 0:
                break
            start = max(0, hit - 90)
            end = min(len(text), hit + len(token) + 120)
            snippet = re.sub(r"\s+", " ", text[start:end]).strip()
            key = snippet.lower()
            if key not in seen:
                seen.add(key)
                snippets.append(snippet)
            idx = hit + len(token)
            if len(snippets) >= 8:
                return snippets
    return snippets
