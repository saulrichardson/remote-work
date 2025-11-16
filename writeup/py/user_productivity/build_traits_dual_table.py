#!/usr/bin/env python3
"""Build a two-panel (OLS + IV) heterogeneity table for the duo-trait spec."""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
PY_DIR = PROJECT_ROOT / "src" / "py"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

from project_paths import RESULTS_CLEANED_TEX, RESULTS_RAW  # type: ignore

RAW_PATH = RESULTS_RAW / "user_productivity_traits_dual_precovid" / "consolidated_results.csv"
OUTPUT_TEX = RESULTS_CLEANED_TEX / "user_productivity_traits_dual_precovid_ols.tex"

STAR_RULES = ((0.01, "***"), (0.05, "**"), (0.10, "*"))
INDENT = r"\hspace{1em}"

PANELS = [
    {"label": "Panel A. OLS", "model_type": "OLS"},
    {"label": "Panel B. IV", "model_type": "IV"},
]

COLUMN_GROUPS = [
    {
        "trait": "female_flag",
        "header": "Female",
        "columns": [
            {"label": "(1)", "fe_tag": "fyhu"},
            {"label": "(2)", "fe_tag": "firmbyuseryh"},
        ],
    },
]

COLUMN_CONFIG: List[Dict[str, str]] = []
for group in COLUMN_GROUPS:
    for column in group["columns"]:
        COLUMN_CONFIG.append(
            {
                "label": column["label"],
                "fe_tag": column["fe_tag"],
                "trait": group["trait"],
                "header": group["header"],
            }
        )

ROW_CONFIG = [
    {
        "label": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
        "param": "var3",
        "trait_key": "baseline",
    },
    {
        "label": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Female} $",
        "param": "var3_female_flag",
        "trait_key": "female_flag",
    },
    {
        "label": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
        "param": "var5",
        "trait_key": "baseline",
    },
    {
        "label": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Female} \times \text{Startup} $",
        "param": "var5_female_flag",
        "trait_key": "female_flag",
    },
]

FE_ROWS = [
    ("Time", {"firmbyuseryh": True, "fyhu": True}),
    ("Firm", {"firmbyuseryh": False, "fyhu": True}),
    ("Individual", {"firmbyuseryh": False, "fyhu": True}),
    (
        r"Firm $\times$ Individual",
        {"firmbyuseryh": True, "fyhu": False},
    ),
]

CHECK_MARK = r"$\checkmark$"


def starify(p: float) -> str:
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""


def format_cell(
    coef: Optional[float], se: Optional[float], pval: Optional[float]
) -> str:
    if coef is None or se is None or pval is None:
        return ""
    return rf"\makecell[c]{{{coef:.2f}{starify(pval)}\\({se:.2f})}}"


LookupKey = Tuple[str, str, str, str]
LookupValue = Tuple[Optional[float], Optional[float], Optional[float]]


def extract_cell(
    lookup: Dict[LookupKey, LookupValue],
    trait_label: str,
    param: str,
    fe_tag: str,
    model_type: str,
) -> str:
    key = (model_type, trait_label, param, fe_tag)
    if key not in lookup:
        return ""
    coef, se, pval = lookup[key]
    if coef is None or se is None or pval is None:
        return ""
    return format_cell(coef, se, pval)


def build_table(lookup: Dict[LookupKey, LookupValue]) -> str:
    col_spec = r"@{}l" + r"@{\extracolsep{\fill}}c" * len(COLUMN_CONFIG) + r"@{}"
    lines: List[str] = [
        r"\centering",
        rf"\begin{{tabular*}}{{\linewidth}}{{{col_spec}}}",
        r"\toprule",
    ]

    lines.append(
        r" & \multicolumn{" + f"{len(COLUMN_CONFIG)}" + r"}{c}{Contribution Rank} \\"
    )
    lines.append(r"\cmidrule(lr){2-" + f"{len(COLUMN_CONFIG)+1}" + r"}")
    lines.append(" & " + " & ".join([col["label"] for col in COLUMN_CONFIG]) + r" \\")
    lines.append(r"\midrule")

    def resolve_trait_and_param(
        row_cfg: Dict[str, object], column: Dict[str, str]
    ) -> Tuple[Optional[str], Optional[str]]:
        if "param_map" in row_cfg:
            param_map = row_cfg.get("param_map", {})
            trait = column["trait"]
            param = param_map.get(trait) if isinstance(param_map, dict) else None
            return trait, param
        trait_key = row_cfg.get("trait_key")
        if trait_key in (None, "", "column"):
            trait = column["trait"]
        else:
            trait = str(trait_key)
        param = row_cfg.get("param")
        param_str = str(param) if isinstance(param, str) else None
        return trait, param_str

    for panel_idx, panel in enumerate(PANELS):
        if panel_idx:
            lines.append(r"\midrule")
        label_text = panel["label"].replace(". ", ": ")
        lines.append(
            rf"\multicolumn{{{len(COLUMN_CONFIG)+1}}}{{@{{}}l}}{{\textbf{{\uline{{{label_text}}}}}}} \\"
        )
        lines.append(r"\addlinespace[2pt]")
        for row_cfg in ROW_CONFIG:
            row = [INDENT + row_cfg["label"]]
            for column in COLUMN_CONFIG:
                trait_label, param = resolve_trait_and_param(row_cfg, column)
                if not trait_label or not param:
                    row.append("")
                    continue
                row.append(
                    extract_cell(
                        lookup,
                        trait_label,
                        param,
                        column["fe_tag"],
                        panel["model_type"],
                    )
                )
            lines.append(" & ".join(row) + r" \\")

    lines.append(r"\midrule")
    lines.append(
        r"\textbf{Fixed Effects} & "
        + " & ".join([""] * len(COLUMN_CONFIG))
        + r" \\"
    )
    for row_label, mapping in FE_ROWS:
        row = [r"\hspace{1em}" + row_label]
        for column in COLUMN_CONFIG:
            row.append(CHECK_MARK if mapping.get(column["fe_tag"], False) else "")
        lines.append(" & ".join(row) + r" \\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular*}")
    return "\n".join(lines) + "\n"


def build_lookup() -> Dict[LookupKey, LookupValue]:
    lookup: Dict[LookupKey, LookupValue] = {}
    if not RAW_PATH.exists():
        raise SystemExit(f"Missing input CSV: {RAW_PATH}")

    with RAW_PATH.open(newline="") as handle:
        reader = csv.DictReader(handle)
        rows = 0
        for row in reader:
            rows += 1
            if row.get("outcome") != "total_contributions_q100":
                continue
            model_type = row.get("model_type")
            trait = row.get("trait")
            param = row.get("param")
            fe_tag = row.get("fe_tag")
            if not all([model_type, trait, param, fe_tag]):
                continue
            lookup[(model_type, trait, param, fe_tag)] = (
                float(row["coef"]) if row.get("coef") not in (None, "") else None,
                float(row["se"]) if row.get("se") not in (None, "") else None,
                float(row["pval"]) if row.get("pval") not in (None, "") else None,
            )
        if rows == 0:
            raise SystemExit(f"No rows found in {RAW_PATH}")
    if not lookup:
        raise SystemExit("No matching rows found for total_contributions_q100.")
    return lookup


def main() -> None:
    lookup = build_lookup()

    OUTPUT_TEX.parent.mkdir(parents=True, exist_ok=True)
    table_tex = build_table(lookup)
    OUTPUT_TEX.write_text(table_tex)
    print(f"Wrote {OUTPUT_TEX}")


if __name__ == "__main__":
    main()
