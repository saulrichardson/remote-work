# Paper Table Builders

This folder is a transitional paper-order reference layer from the earlier
wrapper-based cleanup pass. The canonical build no longer runs these files
directly.

Current canonical behavior:

- `make paper-tables` runs the real cleaned-output builders directly from
  `writeup/py/`
- the source of truth for table formatting lives in domain folders such as
  `writeup/py/user_productivity/`, `writeup/py/firm_scaling/`, and
  `writeup/py/paper_support/`
- `results/cleaned/tex/` is the canonical destination for the regenerated
  paper fragments

What remains here:

- one file per paper table in paper order
- useful as a reference to the earlier wrapper model
- not the place to edit current table-formatting logic

If you are debugging the current canonical pipeline, start in the underlying
builder that `make paper-tables` runs instead of this folder.

Related docs:

- [`../../../docs/paper_table_lineage.md`](../../../docs/paper_table_lineage.md)
- [`../README.md`](../README.md)
