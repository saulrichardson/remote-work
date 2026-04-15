#!/usr/bin/env python3
"""Build horse-race style tables for the "equity as mechanism" approach.

These tables use the LLM-equity *variants* consolidated regression outputs and
present only the *core* remote/startup coefficients (var3 and var5) across
specifications that add equity controls, mirroring existing horse-race tables
in the repo.

Backfill rule: missing/unobserved equity fields are coded as 0 (handled in the
underlying Stata specs).
"""

from __future__ import annotations

import csv
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

# Variants included in the mechanism horse race: these keep the baseline
# triple-diff spec and add equity *controls* (not equity interactions).
SPEC_KEYS: Final[list[str]] = [
    "baseline",
    "eq_any_zero",
    "eq_share_zero",
    "eq_any_firm_covid",
]

SPEC_LABELS: Final[dict[str, str]] = {
    "baseline": r"\makecell[c]{Baseline\\(incl.\ triple term)}",
    "eq_any_zero": r"\makecell[c]{+Equity\\(any, cell)}",
    "eq_share_zero": r"\makecell[c]{+Equity\\(share, cell)}",
    "eq_any_firm_covid": r"\makecell[c]{+EquityFirm\\$\times\mathds{1}(\text{Post})$}",
}

PARAM_LABELS: Final[dict[str, str]] = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
}

FIRM_IN: Final[Path] = RESULTS_RAW / "firm_scaling_llm_equity_variants" / "consolidated_results.csv"
USER_IN: Final[Path] = (
    RESULTS_RAW / "user_productivity_llm_equity_variants_precovid" / "consolidated_results.csv"
)

FIRM_OUT: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_mechanism_variants_firm.tex"
USER_OUT: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_mechanism_variants_user.tex"


def stars(p: float) -> str:
    for cutoff, mark in STAR_RULES:
        if p < cutoff:
            return mark
    return ""


def fmt_coef(value: float) -> str:
    abs_v = abs(value)
    if abs_v >= 1e4:
        return f"{value:.2e}"
    return f"{value:.2f}"


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
    if coef is None or se is None:
        return "--"
    if float(se) == 0.0:
        return "--"
    p = float(pval) if pval is not None else 1.0
    return rf"\makecell[c]{{{fmt_coef(float(coef))}{stars(p)}\\({fmt_coef(float(se))})}}"


def stat_cell(row: dict[str, str] | None, field: str, fmt: str = "{:,.0f}") -> str:
    if row is None:
        return "--"
    value = row.get(field)
    parsed = _to_float(value)
    if parsed is None:
        return "--"
    return fmt.format(parsed)


def tabular_star(colspec: str, body_lines: list[str]) -> str:
    lines = [r"{\centering", rf"\begin{{tabular*}}{{\linewidth}}{{{colspec}}}", TOP]
    lines.extend(body_lines)
    lines.extend([BOTTOM, r"\end{tabular*}", "}"])
    return "\n".join(lines) + "\n"


IndexKey = tuple[str, str, str, str]


def _index_key(*, spec: str, model_type: str, param: str, outcome: str) -> IndexKey:
    return (spec, model_type, param, outcome)


def find_row(index: dict[IndexKey, dict[str, str]], *, spec: str, model_type: str, param: str, outcome: str) -> dict[str, str] | None:
    return index.get(_index_key(spec=spec, model_type=model_type, param=param, outcome=outcome))


def read_consolidated_results(path: Path) -> tuple[dict[IndexKey, dict[str, str]], set[str]]:
    """Read consolidated regression outputs and build a fast lookup index.

    Returns:
      - index: (spec_variant, model_type, param, outcome) -> row dict
      - present_specs: set of spec_variant keys observed in the file
    """
    required_cols = {"spec_variant", "model_type", "param", "outcome"}
    index: dict[IndexKey, dict[str, str]] = {}
    present_specs: set[str] = set()

    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise RuntimeError(f"Empty or invalid CSV (missing header): {path}")
        missing = required_cols.difference(set(reader.fieldnames))
        if missing:
            raise RuntimeError(f"CSV missing required columns {sorted(missing)}: {path}")
        for row in reader:
            spec = (row.get("spec_variant") or "").strip()
            model_type = (row.get("model_type") or "").strip()
            param = (row.get("param") or "").strip()
            outcome = (row.get("outcome") or "").strip()
            if not spec or not model_type or not param or not outcome:
                continue
            present_specs.add(spec)
            index[_index_key(spec=spec, model_type=model_type, param=param, outcome=outcome)] = row

    if not index:
        raise RuntimeError(f"No usable rows read from CSV: {path}")
    return index, present_specs


def build_variants_mechanism_table(
    index: dict[IndexKey, dict[str, str]],
    *,
    outcome: str,
    outcome_header: str,
    fe_lines: list[tuple[str, list[str]]],
    present_specs: set[str],
) -> str:
    # Validate expected specs exist
    missing = [s for s in SPEC_KEYS if s not in present_specs]
    if missing:
        raise RuntimeError(f"Missing expected spec_variant keys: {missing}")

    n_cols = len(SPEC_KEYS)
    colspec = "@{}l" + "@{\\extracolsep{\\fill}}c" * n_cols + "@{}"

    lines: list[str] = [
        " & " + " & ".join(SPEC_LABELS[s] for s in SPEC_KEYS) + LB,
        rf"\cmidrule(lr){{2-{n_cols + 1}}}",
        " & " + " & ".join(f"({i})" for i in range(1, n_cols + 1)) + LB,
        MID,
        rf"\multicolumn{{{n_cols + 1}}}{{@{{}}l}}{{\textbf{{\uline{{Panel A: OLS}}}}}}" + LB,
        r"\addlinespace[2pt]",
    ]

    for param in ["var3", "var5"]:
        cells = [coef_cell(find_row(index, spec=s, model_type="OLS", param=param, outcome=outcome)) for s in SPEC_KEYS]
        lines.append(INDENT + PARAM_LABELS[param] + " & " + " & ".join(cells) + LB)

    lines.append(MID)
    n_ols = [stat_cell(find_row(index, spec=s, model_type="OLS", param="var5", outcome=outcome), "nobs") for s in SPEC_KEYS]
    lines.append("N & " + " & ".join(n_ols) + LB)

    lines.extend(
        [
            MID,
            rf"\multicolumn{{{n_cols + 1}}}{{@{{}}l}}{{\textbf{{\uline{{Panel B: IV}}}}}}" + LB,
            r"\addlinespace[2pt]",
        ]
    )
    for param in ["var3", "var5"]:
        cells = [coef_cell(find_row(index, spec=s, model_type="IV", param=param, outcome=outcome)) for s in SPEC_KEYS]
        lines.append(INDENT + PARAM_LABELS[param] + " & " + " & ".join(cells) + LB)

    lines.append(MID)
    n_iv = [stat_cell(find_row(index, spec=s, model_type="IV", param="var5", outcome=outcome), "nobs") for s in SPEC_KEYS]
    kp = [
        stat_cell(find_row(index, spec=s, model_type="IV", param="var5", outcome=outcome), "rkf", "{:.2f}")
        for s in SPEC_KEYS
    ]
    lines.append("N & " + " & ".join(n_iv) + LB)
    lines.append(r"KP\,rk Wald F & " + " & ".join(kp) + LB)

    checks_all = " & ".join([r"$\checkmark$"] * n_cols)
    lines.extend([MID, r"\textbf{Fixed Effects} & " + " & ".join([""] * n_cols) + LB])
    for label, marks in fe_lines:
        assert len(marks) == n_cols
        lines.append(INDENT + label + " & " + " & ".join(marks) + LB)

    lines.extend([MID, r"\textbf{Equity Controls} & " + " & ".join([""] * n_cols) + LB])
    # Equity control checkmarks by spec
    any_marks = [r"\checkmark" if s == "eq_any_zero" else "" for s in SPEC_KEYS]
    share_marks = [r"\checkmark" if s == "eq_share_zero" else "" for s in SPEC_KEYS]
    firm_post_marks = [r"\checkmark" if s == "eq_any_firm_covid" else "" for s in SPEC_KEYS]
    lines.append(INDENT + r"Equity (any, firm$\times$half-year) & " + " & ".join(any_marks) + LB)
    lines.append(INDENT + r"Equity share (firm$\times$half-year) & " + " & ".join(share_marks) + LB)
    lines.append(INDENT + r"EquityFirm$\times\mathds{1}(\text{Post})$ & " + " & ".join(firm_post_marks) + LB)

    # Outcome label is in caption in the enclosing LaTeX; include only the tabular.
    return tabular_star(colspec, lines)


def main() -> None:
    ensure_dir(RESULTS_CLEANED_TEX)

    firm_path = require_file(FIRM_IN, nonempty=True, purpose="firm equity variants consolidated results")
    user_path = require_file(USER_IN, nonempty=True, purpose="user equity variants consolidated results")

    firm_index, firm_specs = read_consolidated_results(firm_path)
    user_index, user_specs = read_consolidated_results(user_path)

    firm_tex = build_variants_mechanism_table(
        firm_index,
        outcome="growth_rate_we",
        outcome_header="Firm Growth Rate",
        fe_lines=[
            ("Firm", [r"$\checkmark$"] * len(SPEC_KEYS)),
            ("Half-year", [r"$\checkmark$"] * len(SPEC_KEYS)),
        ],
        present_specs=firm_specs,
    )
    user_tex = build_variants_mechanism_table(
        user_index,
        outcome="total_contributions_q100",
        outcome_header="Contribution Rank",
        fe_lines=[
            ("Individual", [r"$\checkmark$"] * len(SPEC_KEYS)),
            ("Firm", [r"$\checkmark$"] * len(SPEC_KEYS)),
            ("Half-year", [r"$\checkmark$"] * len(SPEC_KEYS)),
        ],
        present_specs=user_specs,
    )

    FIRM_OUT.write_text(firm_tex, encoding="utf-8")
    USER_OUT.write_text(user_tex, encoding="utf-8")
    print(f"Wrote {FIRM_OUT}")
    print(f"Wrote {USER_OUT}")


if __name__ == "__main__":
    main()
