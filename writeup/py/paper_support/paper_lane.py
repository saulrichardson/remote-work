#!/usr/bin/env python3
"""Orchestrate the active logic-owned paper asset lane."""

from __future__ import annotations

import argparse
import os
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from writeup.py.paper_support.paper_assets import (
    CONTRACT_PATH,
    PROJECT_ROOT,
    PaperAsset,
    PaperAssetContract,
    load_contract,
    preview_sections,
)

STATA_WRAPPER = PROJECT_ROOT / "bin" / "stata"
PROJECT_PYTHON = PROJECT_ROOT / "bin" / "project-python"
DOC_MAIN_TEX_ASSETS = PROJECT_ROOT / "docs" / "main_tex_assets.md"
DOC_TABLE_LINEAGE = PROJECT_ROOT / "docs" / "paper_table_lineage.md"
DOC_FIGURE_LINEAGE = PROJECT_ROOT / "docs" / "figure_lineage.md"
PREVIEW_TEX = PROJECT_ROOT / "writeup" / "tex" / "main_assets_preview.tex"
FIGURE_FAMILY_TITLES = {
    "core_firm_figures": "Family 1: Core Firm Figures",
    "event_study_figures": "Family 2: Event-Study Figures",
    "startup_cutoff_figures": "Family 3: Startup-Cutoff Figures",
    "irf_figures": "Family 4: Engineer / Non-Engineer IRFs",
    "remote_hire_figures": "Family 5: Remote-Hire Event Study",
}


def _rel(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def _print_command(cmd: Iterable[str]) -> None:
    print("→", " ".join(cmd), flush=True)


def _run(cmd: list[str], *, cwd: Path = PROJECT_ROOT, env: dict[str, str] | None = None) -> None:
    _print_command(cmd)
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def _latex_escape(text: str) -> str:
    return (
        text.replace("\\", r"\textbackslash{}")
        .replace("&", r"\&")
        .replace("%", r"\%")
        .replace("_", r"\_")
        .replace("#", r"\#")
    )


def _format_path_list(paths: Iterable[Path]) -> list[str]:
    return [f"  - `{_rel(path)}`" for path in paths]


def _group_assets_by_family(assets: Iterable[PaperAsset]) -> dict[str, list[PaperAsset]]:
    grouped: dict[str, list[PaperAsset]] = defaultdict(list)
    for asset in sorted(assets, key=lambda item: item.paper_order):
        grouped[asset.family].append(asset)
    return dict(grouped)


def _write(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents)
    print(f"Wrote {_rel(path)}", flush=True)


def render_main_tex_assets_doc(contract: PaperAssetContract) -> str:
    table_assets = list(contract.iter_assets(kind="table"))
    figure_assets = list(contract.iter_assets(kind="figure"))
    excluded_tables = [asset for asset in contract.iter_excluded(kind="table")]
    excluded_figures = [asset for asset in contract.iter_excluded(kind="figure")]
    descriptive_figures = [asset for asset in figure_assets if asset.stata_spec is None]
    estimation_figures = [asset for asset in figure_assets if asset.stata_spec is not None]
    no_stata_tables = [asset for asset in table_assets if asset.stata_spec is None]
    stata_tables = [asset for asset in table_assets if asset.stata_spec is not None]

    lines = [
        "# `main.tex` Logic-Owned Asset Map",
        "",
        "This file is generated from",
        f"`{_rel(CONTRACT_PATH)}` and documents the active logic-owned paper lane only.",
        "",
        f"Active `main.tex` path: `{contract.main_tex_path}`",
        "",
        "## Current active counts",
        "",
        f"- In-scope active table fragments read from `../Results/Tables/`: `{len(table_assets)}`",
        f"- Excluded active table fragments read from `../Results/Tables/`: `{len(excluded_tables)}`",
        f"- In-scope active figure assets read from `../Results/Figures/`: `{len(figure_assets)}`",
        f"- Excluded active figure assets read from `../Figures/`: `{len(excluded_figures)}`",
        "",
        "## Path types inside the active lane",
        "",
        f"- Figures without a Stata owner: `{len(descriptive_figures)}`",
        f"- Figures built from Stata exports in `results/raw/`: `{len(estimation_figures)}`",
        f"- Tables without their own Stata owner: `{len(no_stata_tables)}`",
        f"- Tables built from Stata exports in `results/raw/`: `{len(stata_tables)}`",
        "",
        "Interpretation:",
        "",
        "- descriptive assets can read canonical datasets in `data/clean/` directly",
        "- estimation-driven assets read `results/raw/` exported by `spec/stata/`",
        "- this is intentional; `results/raw/` is the spec-output layer, not the raw-data layer",
        "",
        "## In-scope active figures in paper order",
        "",
    ]

    for asset in figure_assets:
        lines.append(f"{asset.paper_order}. `{asset.cleaned_output.name}`")
        if asset.stata_spec:
            args = " ".join(asset.stata_args)
            suffix = f" {args}".rstrip()
            lines.append(f"   - Stata export: `{_rel(asset.stata_spec)}{suffix}`")
        else:
            lines.append("   - Stata export: none")
        if asset.python_builder:
            args = " ".join(asset.python_args)
            suffix = f" {args}".rstrip()
            lines.append(f"   - Python builder: `{_rel(asset.python_builder)}{suffix}`")
        if asset.raw_outputs:
            for raw_output in asset.raw_outputs:
                lines.append(f"   - Raw output: `{_rel(raw_output)}`")
        if asset.upstream_inputs and not asset.raw_outputs:
            for upstream in asset.upstream_inputs:
                lines.append(f"   - Input: `{_rel(upstream)}`")
        lines.append("")

    lines.extend(
        [
            "## In-scope active tables",
            "",
            f"The `{len(table_assets)}` in-scope active `../Results/Tables/...` fragments are documented in",
            "[`paper_table_lineage.md`](paper_table_lineage.md).",
            "",
            "## Excluded active assets",
            "",
            "These assets are still active in the current Overleaf manuscript, but they are intentionally",
            "outside the repo-owned local build contract. `make data`, `make specs`, and `make paper`",
            "do not generate them.",
            "",
        ]
    )

    for asset in sorted(contract.iter_excluded(), key=lambda item: item.paper_order):
        lines.append(f"- `{asset.main_tex_ref}`")
        lines.append(f"  - Reason: `{asset.reason}`")
        lines.append(f"  - Source: `{asset.current_source}`")
        lines.append(f"  - Note: {asset.notes}")

    lines.extend(
        [
            "",
            "## Current status",
            "",
            "- The active logic-owned paper lane is now derived from one contract file.",
            "- Any active `main.tex` asset not represented in the build is explicit in the exclusion list above.",
            "- `make paper` rebuilds the in-scope cleaned outputs defined by this contract.",
            "",
        ]
    )
    return "\n".join(lines)


def render_table_lineage_doc(contract: PaperAssetContract) -> str:
    table_assets = list(contract.iter_assets(kind="table"))
    excluded_tables = list(contract.iter_excluded(kind="table"))
    stata_backed = [asset for asset in table_assets if asset.stata_spec]
    non_stata = [asset for asset in table_assets if asset.python_builder and not asset.stata_spec]
    downstream_only = [
        asset for asset in table_assets if asset.asset_id == "first_stage_summary"
    ]
    owner_specs = {
        (asset.stata_spec, asset.stata_args)
        for asset in table_assets
        if asset.stata_spec is not None
    }

    lines = [
        "# Paper Table Lineage",
        "",
        "This file is generated from the active logic-owned paper asset contract.",
        "",
        "Grounding:",
        "",
        f"- contract: `{_rel(CONTRACT_PATH)}`",
        f"- Overleaf paper path: `{contract.main_tex_path}`",
        "- active table-side Stata implementations under `spec/stata/tables/`",
        "- active Python builders under `writeup/py/`",
        "- raw outputs under `results/raw/`",
        "- cleaned table fragments under `results/cleaned/tex/`",
        "",
        "## Counts",
        "",
        f"- In-scope active table fragments in `main.tex`: `{len(table_assets)}`",
        f"- In-scope fragments built from active Stata exports: `{len(stata_backed)}`",
        f"- Active table-side logical owners in this repo-owned lane: `{len(owner_specs)}`",
        f"- In-scope table assets without their own Stata owner: `{len(non_stata)}`",
        f"- Downstream-only in-scope table assets: `{len(downstream_only)}`",
        f"- Excluded active table assets: `{len(excluded_tables)}`",
        "",
        "## Input modes",
        "",
        "- Descriptive or hybrid tables without their own Stata owner:",
        "  - `table_of_means.tex` reads canonical cleaned data directly and also uses the upstream",
        "    postings-equity branch",
        "  - `first_stage_summary.tex` is downstream-only and summarizes already-exported spec outputs",
        "- Estimation-driven tables:",
        "  - the remaining in-scope tables run through `spec/stata/tables/` and read `results/raw/`",
        "",
        "## In-scope active tables in paper order",
        "",
    ]

    for asset in table_assets:
        lines.append(f"{asset.paper_order}. `{asset.cleaned_output.name}`")
        if asset.stata_spec:
            args = " ".join(asset.stata_args)
            suffix = f" {args}".rstrip()
            lines.append(f"   - Stata: `{_rel(asset.stata_spec)}{suffix}`")
        else:
            lines.append("   - Stata: none")
        if asset.raw_outputs:
            for raw_output in asset.raw_outputs:
                lines.append(f"   - Raw output: `{_rel(raw_output)}`")
        if asset.python_builder:
            args = " ".join(asset.python_args)
            suffix = f" {args}".rstrip()
            lines.append(f"   - Python builder: `{_rel(asset.python_builder)}{suffix}`")
        if asset.upstream_inputs:
            for upstream in asset.upstream_inputs:
                lines.append(f"   - Upstream input: `{_rel(upstream)}`")
        lines.append("")

    lines.extend(
        [
            "## Excluded active table assets",
            "",
            "These table assets are still active in the manuscript, but they are intentionally outside",
            "the repo-owned local build contract. The public local commands do not generate them.",
            "",
        ]
    )
    for asset in excluded_tables:
        lines.append(f"- `{asset.main_tex_ref}`")
        lines.append(f"  - Reason: `{asset.reason}`")
        lines.append(f"  - Source: `{asset.current_source}`")
        lines.append(f"  - Note: {asset.notes}")

    lines.extend(
        [
            "",
            "## Current status",
            "",
            "- The in-scope table lane is driven from one asset contract and no longer from hand-maintained build lists.",
            "- `Final.tex` remains explicit but excluded because its empirical generator is not recovered in the repo.",
            "",
        ]
    )
    return "\n".join(lines)


def render_figure_lineage_doc(contract: PaperAssetContract) -> str:
    figure_assets = list(contract.iter_assets(kind="figure"))
    excluded_figures = list(contract.iter_excluded(kind="figure"))
    grouped = _group_assets_by_family(figure_assets)

    lines = [
        "# Figure Lineage",
        "",
        "This document is generated from the active logic-owned paper asset contract.",
        "",
        "It answers three questions:",
        "",
        "1. which active Stata scripts feed the in-scope figures",
        "2. which active Python builders render the final images",
        "3. where the final cleaned files are written",
        "",
        "For the exact active `main.tex` inventory, start with",
        "[`main_tex_assets.md`](main_tex_assets.md).",
        "",
        "## Active output locations",
        "",
    ]
    for root in contract.metadata.cleaned_roots:
        lines.append(f"- `{_rel(root)}`")
    lines.extend(
        [
            "",
            "## Input modes",
            "",
            "- Descriptive figures:",
            "  - the core firm figures have no Stata owner and read canonical cleaned datasets",
            "    directly from `data/clean/`",
            "- Estimation-driven figures:",
            "  - all remaining in-scope figures run through `spec/stata/figures/`, write",
            "    machine-readable outputs to `results/raw/`, and then render final PNGs from there",
            "",
        ]
    )

    for family in FIGURE_FAMILY_TITLES:
        assets = grouped.get(family, [])
        if not assets:
            continue
        lines.append(f"## {FIGURE_FAMILY_TITLES[family]}")
        lines.append("")
        for asset in assets:
            lines.append(f"- `{asset.cleaned_output.name}`")
            if asset.stata_spec:
                args = " ".join(asset.stata_args)
                suffix = f" {args}".rstrip()
                lines.append(f"  - Stata: `{_rel(asset.stata_spec)}{suffix}`")
            else:
                lines.append("  - Stata: none")
            if asset.python_builder:
                lines.append(f"  - Python builder: `{_rel(asset.python_builder)}`")
            if asset.raw_outputs:
                for raw_output in asset.raw_outputs:
                    lines.append(f"  - Raw output: `{_rel(raw_output)}`")
            if asset.upstream_inputs and not asset.raw_outputs:
                for upstream in asset.upstream_inputs:
                    lines.append(f"  - Input: `{_rel(upstream)}`")
        lines.append("")

    lines.extend(
        [
            "## Excluded active figures",
            "",
            "These figure assets are still active in the manuscript, but they are intentionally outside",
            "the repo-owned local build contract. The public local commands do not generate them.",
            "",
        ]
    )
    for asset in excluded_figures:
        lines.append(f"- `{asset.main_tex_ref}`")
        lines.append(f"  - Reason: `{asset.reason}`")
        lines.append(f"  - Source: `{asset.current_source}`")
        lines.append(f"  - Note: {asset.notes}")
    lines.extend(
        [
            "",
            "## Status",
            "",
            "- The active logic-owned figure lane reruns from the contract-defined Stata and Python surface.",
            "- Any active external figure still used by the manuscript is explicit in the exclusion section above.",
            "",
        ]
    )
    return "\n".join(lines)


def render_preview_tex(contract: PaperAssetContract) -> str:
    lines = [
        r"\documentclass{article}",
        r"\usepackage[margin=1in]{geometry}",
        r"\usepackage{float}",
        r"\usepackage{graphicx}",
        r"\usepackage{caption}",
        r"\usepackage{booktabs}",
        r"\usepackage{makecell}",
        r"\usepackage[normalem]{ulem}",
        r"\usepackage{textcomp}",
        r"\usepackage{amsmath,amssymb,amsfonts}",
        r"\usepackage{dsfont}",
        r"\usepackage{pdflscape}",
        "",
        r"\newcommand{\TableInput}[2][\linewidth]{\input{#2}}",
        r"\providecommand{\mathbbm}[1]{\mathds{#1}}",
        "",
        r"\begin{document}",
        "",
        r"\section*{Logic-Owned `main.tex` Asset Preview}",
        "",
        r"This preview is generated from the active logic-owned paper asset contract. It includes only",
        r"the in-scope tables and figures rebuilt by this repo and omits active manuscript assets that are",
        r"explicitly excluded from the logic-owned lane.",
        "",
    ]

    appendix_open = False
    for section, assets in preview_sections(contract):
        if section.startswith("Appendix") and not appendix_open:
            lines.extend(
                [
                    r"\clearpage",
                    r"\appendix",
                ]
            )
            appendix_open = True

        lines.append(rf"\section*{{{_latex_escape(section)}}}")
        lines.append("")
        for asset in assets:
            preview_path = Path(os.path.relpath(asset.cleaned_output, PREVIEW_TEX.parent)).as_posix()
            if asset.kind == "figure":
                lines.extend(
                    [
                        r"\begin{figure}[H]\centering",
                        rf"  \caption{{{_latex_escape(asset.preview_caption)}}}",
                        rf"  \includegraphics[width=.85\linewidth]{{{preview_path}}}",
                        r"\end{figure}",
                        "",
                    ]
                )
            else:
                lines.extend(
                    [
                        r"\begin{table}[H]\centering",
                        rf"  \caption{{{_latex_escape(asset.preview_caption)}}}",
                        rf"  \TableInput{{{preview_path}}}",
                        r"\end{table}",
                        "",
                    ]
                )

    lines.extend(
        [
            r"\section*{Excluded Active Assets}",
            "",
            r"The current manuscript still reads the following active assets outside the logic-owned lane:",
            "",
            r"\begin{itemize}",
        ]
    )
    for asset in contract.iter_excluded():
        lines.append(rf"\item \texttt{{{_latex_escape(asset.main_tex_ref)}}} ({_latex_escape(asset.reason)})")
    lines.extend(
        [
            r"\end{itemize}",
            "",
            r"\end{document}",
            "",
        ]
    )
    return "\n".join(lines)


def render_contract(contract: PaperAssetContract) -> None:
    _write(DOC_MAIN_TEX_ASSETS, render_main_tex_assets_doc(contract))
    _write(DOC_TABLE_LINEAGE, render_table_lineage_doc(contract))
    _write(DOC_FIGURE_LINEAGE, render_figure_lineage_doc(contract))
    _write(PREVIEW_TEX, render_preview_tex(contract))


def _dedupe_commands(assets: Iterable[PaperAsset], *, builder_kind: str) -> list[list[str]]:
    commands: list[list[str]] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for asset in sorted(assets, key=lambda item: item.paper_order):
        if builder_kind == "stata":
            executable = asset.stata_spec
            args = asset.stata_args
            if executable is None:
                continue
            key = (_rel(executable), args)
            if key in seen:
                continue
            seen.add(key)
            commands.append([str(STATA_WRAPPER), "-b", "do", str(executable), *args])
        else:
            executable = asset.python_builder
            args = asset.python_args
            if executable is None:
                continue
            key = (_rel(executable), args)
            if key in seen:
                continue
            seen.add(key)
            commands.append([str(PROJECT_PYTHON), str(executable), *args])
    return commands


def run_stata_assets(contract: PaperAssetContract, *, kind: str) -> None:
    for cmd in _dedupe_commands(contract.iter_assets(kind=kind), builder_kind="stata"):
        _run(cmd)


def run_python_assets(contract: PaperAssetContract, *, kind: str) -> None:
    for cmd in _dedupe_commands(contract.iter_assets(kind=kind), builder_kind="python"):
        _run(cmd)

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("render-contract", help="Regenerate docs and preview inputs from the active contract.")

    for name, help_text in (
        ("run-stata", "Run active Stata owners."),
        ("run-python", "Run active Python builders."),
    ):
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("--kind", choices=("table", "figure"), required=True)

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    contract = load_contract()

    if args.command == "render-contract":
        render_contract(contract)
        return
    if args.command == "run-stata":
        run_stata_assets(contract, kind=args.kind)
        return
    if args.command == "run-python":
        run_python_assets(contract, kind=args.kind)
        return
    raise RuntimeError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    main()
