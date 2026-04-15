#!/usr/bin/env python3
"""Helpers for the active logic-owned paper asset contract."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from src.py.project_paths import PROJECT_ROOT

CONTRACT_PATH = Path(__file__).resolve().with_name("paper_asset_contract.json")

RESULTS_TABLE_PREFIX = "../Results/Tables/"
RESULTS_FIGURE_PREFIX = "../Results/Figures/"
EXTERNAL_FIGURE_PREFIX = "../Figures/"
RELEVANT_MAIN_TEX_PREFIXES = (
    RESULTS_TABLE_PREFIX,
    RESULTS_FIGURE_PREFIX,
    EXTERNAL_FIGURE_PREFIX,
)
PREVIEW_SECTION_ORDER = (
    "Main Figures",
    "Main Tables",
    "Appendix Figures",
    "Appendix Tables",
)


@dataclass(frozen=True)
class RequiredStataPackage:
    name: str
    install: str


@dataclass(frozen=True)
class AssetMetadata:
    contract_version: int
    main_tex_path: Path
    generated_docs: tuple[Path, ...]
    cleaned_roots: tuple[Path, ...]
    required_python_modules: tuple[str, ...]
    required_stata_packages: tuple[RequiredStataPackage, ...]


@dataclass(frozen=True)
class PaperAsset:
    asset_id: str
    kind: str
    paper_order: int
    main_tex_ref: str
    cleaned_output: Path
    preview_section: str
    preview_caption: str
    family: str
    stata_spec: Path | None
    stata_args: tuple[str, ...]
    python_builder: Path | None
    python_args: tuple[str, ...]
    raw_outputs: tuple[Path, ...]
    upstream_inputs: tuple[Path, ...]

    @property
    def cleaned_output_rel(self) -> str:
        return self.cleaned_output.relative_to(PROJECT_ROOT).as_posix()


@dataclass(frozen=True)
class ExcludedPaperAsset:
    asset_id: str
    kind: str
    paper_order: int
    main_tex_ref: str
    reason: str
    current_source: str
    notes: str


@dataclass(frozen=True)
class PaperAssetContract:
    metadata: AssetMetadata
    active_assets: tuple[PaperAsset, ...]
    excluded_assets: tuple[ExcludedPaperAsset, ...]

    def iter_assets(self, *, kind: str | None = None) -> Iterable[PaperAsset]:
        assets = sorted(self.active_assets, key=lambda asset: asset.paper_order)
        if kind is None:
            return tuple(assets)
        return tuple(asset for asset in assets if asset.kind == kind)

    def iter_excluded(self, *, kind: str | None = None) -> Iterable[ExcludedPaperAsset]:
        assets = sorted(self.excluded_assets, key=lambda asset: asset.paper_order)
        if kind is None:
            return tuple(assets)
        return tuple(asset for asset in assets if asset.kind == kind)

    @property
    def main_tex_path(self) -> Path:
        return self.metadata.main_tex_path


def _project_path(value: str) -> Path:
    return (PROJECT_ROOT / value).resolve()


def _load_metadata(raw: dict) -> AssetMetadata:
    return AssetMetadata(
        contract_version=int(raw["contract_version"]),
        main_tex_path=Path(raw["main_tex_path"]).expanduser().resolve(),
        generated_docs=tuple(_project_path(path) for path in raw["generated_docs"]),
        cleaned_roots=tuple(_project_path(path) for path in raw["cleaned_roots"]),
        required_python_modules=tuple(raw.get("required_python_modules", [])),
        required_stata_packages=tuple(
            RequiredStataPackage(name=item["name"], install=item["install"])
            for item in raw.get("required_stata_packages", [])
        ),
    )


def _load_asset(raw: dict) -> PaperAsset:
    stata_spec = raw.get("stata_spec")
    python_builder = raw.get("python_builder")
    return PaperAsset(
        asset_id=raw["id"],
        kind=raw["kind"],
        paper_order=int(raw["paper_order"]),
        main_tex_ref=raw["main_tex_ref"],
        cleaned_output=_project_path(raw["cleaned_output"]),
        preview_section=raw["preview_section"],
        preview_caption=raw["preview_caption"],
        family=raw["family"],
        stata_spec=_project_path(stata_spec) if stata_spec else None,
        stata_args=tuple(raw.get("stata_args", [])),
        python_builder=_project_path(python_builder) if python_builder else None,
        python_args=tuple(raw.get("python_args", [])),
        raw_outputs=tuple(_project_path(path) for path in raw.get("raw_outputs", [])),
        upstream_inputs=tuple(_project_path(path) for path in raw.get("upstream_inputs", [])),
    )


def _load_excluded(raw: dict) -> ExcludedPaperAsset:
    return ExcludedPaperAsset(
        asset_id=raw["id"],
        kind=raw["kind"],
        paper_order=int(raw["paper_order"]),
        main_tex_ref=raw["main_tex_ref"],
        reason=raw["reason"],
        current_source=raw["current_source"],
        notes=raw["notes"],
    )


def load_contract() -> PaperAssetContract:
    payload = json.loads(CONTRACT_PATH.read_text())
    metadata = _load_metadata(payload["metadata"])
    active_assets = tuple(_load_asset(item) for item in payload["active_assets"])
    excluded_assets = tuple(_load_excluded(item) for item in payload["excluded_assets"])
    return PaperAssetContract(
        metadata=metadata,
        active_assets=active_assets,
        excluded_assets=excluded_assets,
    )


def strip_latex_comments(text: str) -> str:
    """Return *text* with unescaped LaTeX comments removed."""
    stripped_lines: list[str] = []
    for line in text.splitlines():
        current: list[str] = []
        escaped = False
        for char in line:
            if char == "%" and not escaped:
                break
            current.append(char)
            escaped = char == "\\" and not escaped
            if char != "\\":
                escaped = False
        stripped_lines.append("".join(current))
    return "\n".join(stripped_lines)


def parse_relevant_main_tex_refs(path: Path) -> list[str]:
    import re

    cleaned = strip_latex_comments(path.read_text())
    pattern = re.compile(
        r"\\(?:includegraphics(?:\[[^\]]*\])?|TableInput(?:\[[^\]]*\])?)\{([^}]+)\}"
    )
    refs = [match.group(1) for match in pattern.finditer(cleaned)]
    return [
        ref
        for ref in refs
        if ref.startswith(RELEVANT_MAIN_TEX_PREFIXES)
    ]


def expected_active_refs(contract: PaperAssetContract) -> list[str]:
    return [asset.main_tex_ref for asset in contract.iter_assets()]


def expected_excluded_refs(contract: PaperAssetContract) -> list[str]:
    return [asset.main_tex_ref for asset in contract.iter_excluded()]


def expected_cleaned_outputs(contract: PaperAssetContract, *, kind: str | None = None) -> list[Path]:
    return [asset.cleaned_output for asset in contract.iter_assets(kind=kind)]


def preview_sections(contract: PaperAssetContract) -> list[tuple[str, list[PaperAsset]]]:
    active_assets = list(contract.iter_assets())
    sections: list[tuple[str, list[PaperAsset]]] = []
    for section in PREVIEW_SECTION_ORDER:
        scoped = [asset for asset in active_assets if asset.preview_section == section]
        if scoped:
            sections.append((section, scoped))
    return sections


__all__ = [
    "PROJECT_ROOT",
    "CONTRACT_PATH",
    "RESULTS_TABLE_PREFIX",
    "RESULTS_FIGURE_PREFIX",
    "EXTERNAL_FIGURE_PREFIX",
    "RELEVANT_MAIN_TEX_PREFIXES",
    "PREVIEW_SECTION_ORDER",
    "PaperAsset",
    "ExcludedPaperAsset",
    "PaperAssetContract",
    "load_contract",
    "parse_relevant_main_tex_refs",
    "expected_active_refs",
    "expected_excluded_refs",
    "expected_cleaned_outputs",
    "preview_sections",
]
