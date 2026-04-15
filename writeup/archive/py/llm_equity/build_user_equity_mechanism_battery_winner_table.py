#!/usr/bin/env python3
"""Render a compact horse-race table from the equity mechanism *battery* (user).

Goal:
  - Show baseline vs a very small set of equity mechanism controls from the
    battery run, reporting *all* coefficients estimated in the horse race:
      - Remote×Post (var3)
      - Remote×Post×Startup (var5)
      - Startup×Post (var4)
      - Post×EquityExposure and Post×EquityExposure×Startup (controls)
  - Match the *horse race* table style used elsewhere in the repo:
      - Column numbers only (no long headers)
      - A bottom panel describing fixed effects

This is for the *pair-FE* user productivity design:
  absorb(firm_id#user_id yh), cluster(user_id)
"""

from __future__ import annotations

import csv
import argparse
import sys
from pathlib import Path
from typing import Final

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
PY_DIR = PROJECT_ROOT / "src" / "py"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

from project_paths import RESULTS_CLEANED_TEX, RESULTS_RAW, ensure_dir, require_file

LB: Final[str] = r" \\"
TOP: Final[str] = r"\toprule"
MID: Final[str] = r"\midrule"
BOTTOM: Final[str] = r"\bottomrule"
INDENT: Final[str] = r"\hspace{1em}"

STAR_RULES: Final[list[tuple[float, str]]] = [(0.01, "***"), (0.05, "**"), (0.10, "*")]

SAMPLE_MODE: Final[str] = "all"
OUTCOME: Final[str] = "total_contributions_q100"
OUT_TEX_K_ANY: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_user_mechanism_battery_winner.tex"
OUT_TEX_K_ANY_BASELINE_FE: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_user_mechanism_battery_winner_baselinefe.tex"

OUT_TEX_SHARE_POSTINGS: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_user_mechanism_battery_share_postings.tex"
OUT_TEX_SHARE_POSTINGS_BASELINE_FE: Final[Path] = (
    RESULTS_CLEANED_TEX / "llm_equity_user_mechanism_battery_share_postings_baselinefe.tex"
)

VARIANT_CONFIG: Final[dict[str, dict[str, object]]] = {
    "r_any_ever": {
        "spec_keys": ["baseline", "r_any_ever"],
        "z_desc": "Offers equity",
        "out_pair": OUT_TEX_K_ANY,
        "out_baseline": OUT_TEX_K_ANY_BASELINE_FE,
    },
    "r_shp_post": {
        "spec_keys": ["baseline", "r_shp_post"],
        "z_desc": "Share of postings offering equity",
        "out_pair": OUT_TEX_SHARE_POSTINGS,
        "out_baseline": OUT_TEX_SHARE_POSTINGS_BASELINE_FE,
    },
}


def stars(p: float) -> str:
    for cutoff, mark in STAR_RULES:
        if p < cutoff:
            return mark
    return ""


def fmt_num(x: float) -> str:
    ax = abs(x)
    if ax >= 1e4:
        return f"{x:.2e}"
    return f"{x:.2f}"


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    v = str(value).strip()
    if v == "" or v.lower() in {"nan", "na", "none"}:
        return None
    return float(v)


def coef_cell(row: dict[str, str] | None) -> str:
    if row is None:
        return "--"
    coef = _to_float(row.get("coef"))
    se = _to_float(row.get("se"))
    pval = _to_float(row.get("pval"))
    if coef is None or se is None or float(se) == 0.0:
        return "--"
    p = float(pval) if pval is not None else 1.0
    return rf"\makecell[c]{{{fmt_num(float(coef))}{stars(p)}\\({fmt_num(float(se))})}}"


def stat_cell(row: dict[str, str] | None, field: str, fmt: str = "{:,.0f}") -> str:
    if row is None:
        return "--"
    value = row.get(field)
    parsed = _to_float(value)
    if parsed is None:
        return "--"
    return fmt.format(parsed)

IndexKey = tuple[str, str, str, str, str]


def _index_key(*, sample_mode: str, spec: str, model_type: str, outcome: str, param: str) -> IndexKey:
    return (sample_mode, spec, model_type, outcome, param)


def read_results(path: Path) -> tuple[dict[IndexKey, dict[str, str]], set[str]]:
    required = {"model_type", "sample_mode", "spec_variant", "outcome", "param"}
    index: dict[IndexKey, dict[str, str]] = {}
    present_specs: set[str] = set()

    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise RuntimeError(f"Empty/invalid CSV (missing header): {path}")
        missing = required.difference(set(reader.fieldnames))
        if missing:
            raise RuntimeError(f"CSV missing required columns {sorted(missing)}: {path}")

        for row in reader:
            sample_mode = (row.get("sample_mode") or "").strip()
            spec = (row.get("spec_variant") or "").strip()
            model_type = (row.get("model_type") or "").strip()
            outcome = (row.get("outcome") or "").strip()
            param = (row.get("param") or "").strip()
            if not sample_mode or not spec or not model_type or not outcome or not param:
                continue
            present_specs.add(spec)
            index[_index_key(sample_mode=sample_mode, spec=spec, model_type=model_type, outcome=outcome, param=param)] = row

    if not index:
        raise RuntimeError(f"No usable rows read from CSV: {path}")
    return index, present_specs


def find_row(
    index: dict[IndexKey, dict[str, str]],
    *,
    spec: str,
    model_type: str,
    param: str,
) -> dict[str, str] | None:
    return index.get(
        _index_key(sample_mode=SAMPLE_MODE, spec=spec, model_type=model_type, outcome=OUTCOME, param=param)
    )


def tabular_star(colspec: str, body_lines: list[str]) -> str:
    lines = [r"{\centering", rf"\begin{{tabular*}}{{\linewidth}}{{{colspec}}}", TOP]
    lines.extend(body_lines)
    lines.extend([BOTTOM, r"\end{tabular*}", "}"])
    return "\n".join(lines) + "\n"


def build_table(
    index: dict[IndexKey, dict[str, str]],
    present_specs: set[str],
    *,
    spec_keys: list[str],
    z_desc: str,
) -> str:
    missing = [s for s in spec_keys if s not in present_specs]
    if missing:
        raise RuntimeError(f"Missing expected spec_variant keys in input CSV: {missing}")

    n_cols = len(spec_keys)
    colspec = "@{}l" + "@{\\extracolsep{\\fill}}c" * n_cols + "@{}"

    param_labels: dict[str, str] = {
        "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
        "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
        "var4": r"$ \text{Startup} \times \mathds{1}(\text{Post}) $",
        "z_main": rf"$ \mathds{{1}}(\text{{Post}}) \times \text{{{z_desc}}} $",
        "z_su": rf"$ \mathds{{1}}(\text{{Post}}) \times \text{{{z_desc}}} \times \text{{Startup}} $",
    }

    lines: list[str] = [
        rf" & \multicolumn{{{n_cols}}}{{c}}{{Contribution Rank}}" + LB,
        rf"\cmidrule(lr){{2-{n_cols + 1}}}",
        " & " + " & ".join(f"({i})" for i in range(1, n_cols + 1)) + LB,
        MID,
        rf"\multicolumn{{{n_cols + 1}}}{{@{{}}l}}{{\textbf{{\uline{{Panel A: OLS}}}}}}" + LB,
        r"\addlinespace[2pt]",
    ]

    def _param_for_spec(param: str, spec: str) -> str:
        if param == "z_main":
            return f"z_{spec}"
        if param == "z_su":
            return f"z_{spec}_su"
        return param

    params = ["var3", "var5", "var4", "z_main", "z_su"]
    for param in params:
        label = param_labels[param]
        cells = [
            coef_cell(find_row(index, spec=s, model_type="OLS", param=_param_for_spec(param, s))) for s in spec_keys
        ]
        lines.append(INDENT + label + " & " + " & ".join(cells) + LB)

    lines.append(MID)
    n_ols = [stat_cell(find_row(index, spec=s, model_type="OLS", param="var5"), "nobs") for s in spec_keys]
    lines.append("N & " + " & ".join(n_ols) + LB)

    lines.extend(
        [
            MID,
            rf"\multicolumn{{{n_cols + 1}}}{{@{{}}l}}{{\textbf{{\uline{{Panel B: IV}}}}}}" + LB,
            r"\addlinespace[2pt]",
        ]
    )
    for param in params:
        label = param_labels[param]
        cells = [
            coef_cell(find_row(index, spec=s, model_type="IV", param=_param_for_spec(param, s))) for s in spec_keys
        ]
        lines.append(INDENT + label + " & " + " & ".join(cells) + LB)

    lines.append(MID)
    n_iv = [stat_cell(find_row(index, spec=s, model_type="IV", param="var5"), "nobs") for s in spec_keys]
    kp = [stat_cell(find_row(index, spec=s, model_type="IV", param="var5"), "rkf", "{:.2f}") for s in spec_keys]
    lines.append("N & " + " & ".join(n_iv) + LB)
    lines.append(r"KP\,rk Wald F & " + " & ".join(kp) + LB)

    lines.extend([MID, r"\textbf{Fixed Effects} & " + " & ".join([""] * n_cols) + LB])
    # Filled in by caller (pair FE vs baseline FE)

    return tabular_star(colspec, lines)


def _battery_results_dir(panel_variant: str, fe_mode: str) -> Path:
    if fe_mode == "pair":
        return RESULTS_RAW / f"user_productivity_llm_equity_mechanism_battery_{panel_variant}"
    if fe_mode == "baseline":
        return RESULTS_RAW / f"user_productivity_llm_equity_mechanism_battery_baselinefe_{panel_variant}"
    raise ValueError(f"Unknown fe_mode: {fe_mode}")


def _insert_fe_block(tex: str, *, fe_mode: str) -> str:
    """Insert FE checkmark lines under the Fixed Effects header.

    We generate the main table body without hard-coding FE structure, then
    splice in the appropriate FE rows.
    """
    lines = tex.splitlines()
    out: list[str] = []
    injected = False
    for line in lines:
        out.append(line)
        if (not injected) and line.strip() == r"\textbf{Fixed Effects} &  &  \\":
            if fe_mode == "pair":
                out.append(INDENT + r"Time" + r" & $\checkmark$ & $\checkmark$ \\")
                out.append(INDENT + r"Firm $\times$ Individual" + r" & $\checkmark$ & $\checkmark$ \\")
            elif fe_mode == "baseline":
                out.append(INDENT + r"Time" + r" & $\checkmark$ & $\checkmark$ \\")
                out.append(INDENT + r"Firm" + r" & $\checkmark$ & $\checkmark$ \\")
                out.append(INDENT + r"Individual" + r" & $\checkmark$ & $\checkmark$ \\")
            else:
                raise ValueError(f"Unknown fe_mode: {fe_mode}")
            injected = True
    if not injected:
        raise RuntimeError("Failed to inject FE block: Fixed Effects header not found.")
    return "\n".join(out) + ("\n" if tex.endswith("\n") else "")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build equity mechanism battery winner horse-race table.")
    parser.add_argument("--panel", default="precovid", help="Panel variant (e.g., precovid).")
    parser.add_argument("--fe", default="pair", choices=["pair", "baseline"], help="Fixed effects mode.")
    parser.add_argument(
        "--variant",
        default="r_any_ever",
        choices=sorted(VARIANT_CONFIG.keys()),
        help="Which equity control variant to render (baseline always included).",
    )
    return parser.parse_args()


def main() -> None:
    ensure_dir(RESULTS_CLEANED_TEX)
    args = parse_args()
    in_path = require_file(
        _battery_results_dir(args.panel, args.fe) / "consolidated_results.csv",
        nonempty=True,
        purpose="battery consolidated_results.csv",
    )
    index, present_specs = read_results(in_path)
    cfg = VARIANT_CONFIG[args.variant]
    spec_keys = list(cfg["spec_keys"])  # type: ignore[arg-type]
    z_desc = str(cfg["z_desc"])
    tex = build_table(index, present_specs, spec_keys=spec_keys, z_desc=z_desc)
    tex = _insert_fe_block(tex, fe_mode=args.fe)

    out_path = Path(cfg["out_pair"] if args.fe == "pair" else cfg["out_baseline"])  # type: ignore[arg-type]
    out_path.write_text(tex, encoding="utf-8")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
