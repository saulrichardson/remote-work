# Paper Stata Wrappers

This folder is a transitional reference layer from the earlier wrapper-based
cleanup pass. The canonical build no longer runs these files.

Current canonical behavior:

- `make paper-specs` runs the real Stata implementations directly from
  `spec/stata/`
- numbered top-level specs in `spec/stata/` are the source of truth where a
  paper result already maps cleanly to one real implementation
- a few shared legacy specs are still run directly from `spec/stata/` where
  multiple paper tables depend on the same raw exports

What remains here:

- thin orchestration shims in paper order
- useful as a paper-order reference when tracing the earlier cleanup pass
- not the place to edit current regression logic

If you are debugging the current canonical pipeline, start in top-level
`spec/stata/` instead of this folder.

Related docs:

- [`../../../docs/paper_table_lineage.md`](../../../docs/paper_table_lineage.md)
- [`../README.md`](../README.md)
