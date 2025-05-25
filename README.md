# Repository Documentation

The canonical documentation is maintained in a \LaTeX\ source file and
compiled to the PDF that lives next to this stub.

👉  **Open `README.pdf` for a fully formatted, up-to-date overview of the
project, its directory structure, and the end-to-end workflow.**

If you need to rebuild the PDF, simply run

```bash
# quick rebuild
make -C writeup readme
```

from the repository root (the command requires a standard \TeX\ Live
installation plus \texttt{pygmentize} for syntax highlighting).

## Data Samples

Scripts in `py/` expect CSV files under `data/samples/`:

* `firm_panel.csv`
* `user_panel.csv`  (formerly `worker_panel.csv`)
