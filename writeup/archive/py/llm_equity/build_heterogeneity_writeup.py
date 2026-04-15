#!/usr/bin/env python3
"""Build a standalone LaTeX note for LLM-equity heterogeneity results."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
PY_DIR = PROJECT_ROOT / "src" / "py"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

from project_paths import RESULTS_CLEANED_TEX, ensure_dir, require_file

FIRM_TEX = RESULTS_CLEANED_TEX / "firm_scaling_llm_equity_heterogeneity.tex"
USER_TEX = RESULTS_CLEANED_TEX / "user_productivity_llm_equity_heterogeneity_precovid.tex"

OUT_TEX = PROJECT_ROOT / "writeup" / "tex" / "llm_equity_heterogeneity_note.tex"

def main() -> None:
    require_file(FIRM_TEX, nonempty=True, purpose="firm heterogeneity LaTeX table")
    require_file(USER_TEX, nonempty=True, purpose="user heterogeneity LaTeX table")

    content = rf"""\documentclass{{article}}
\usepackage[margin=1.15in]{{geometry}}
\usepackage{{booktabs}}
\usepackage{{makecell}}
\usepackage{{float}}
\usepackage{{amsmath,amssymb,amsfonts}}
\usepackage{{dsfont}}
\usepackage[normalem]{{ulem}}

\newcommand{{\cleanedresultsdir}}{{../results/cleaned/tex}}
\newcommand{{\TableInput}}[2][\linewidth]{{\input{{#2}}}}

\begin{{document}}

\section*{{LLM Equity Heterogeneity: Interaction + Split}}

This note reports the default-spec heterogeneity design for the two core outcomes:
\texttt{{firm\_scaling}} and \texttt{{user\_productivity\_precovid}}. Both keep the core FE and IV setups and add:
(i) a pooled interaction model with equity-firm interactions, and
(ii) split baseline models for non-equity vs equity firms.

\subsection*{{Variables and construction}}
\begin{{itemize}}
  \item \textbf{{Core treatment terms (already in baseline specs).}}
  \texttt{{var3 = remote $\times$ covid}}, \texttt{{var5 = remote $\times$ covid $\times$ startup}},
  \texttt{{var4 = covid $\times$ startup}}.
  For IV, \texttt{{var6 = covid $\times$ teleworkable}} and
  \texttt{{var7 = startup $\times$ covid $\times$ teleworkable}}.

  \item \textbf{{LLM equity signal at firm$\times$half-year.}}
  The merge panel (\texttt{{latest\_firm\_yh\_llm\_equity.csv}}) contributes
  \texttt{{llm\_n\_parse\_ok}} and \texttt{{llm\_equity\_any}}.
  In construction: \texttt{{eq\_has\_parse = 1[llm\_n\_parse\_ok>0]}},
  \texttt{{eq\_any\_obs = llm\_equity\_any}} only when parse is available,
  then \texttt{{eq\_any\_firm = max(eq\_any\_obs)}} within firm over time
  (missing set to 0), and \texttt{{eq\_any\_firm\_covid = eq\_any\_firm $\times$ covid}}.

  \item \textbf{{Pooled interaction design.}}
  Add interaction regressors
  \texttt{{var3\_eq\_firm = var3 $\times$ eq\_any\_firm}} and
  \texttt{{var5\_eq\_firm = var5 $\times$ eq\_any\_firm}}.
  IV instruments these with
  \texttt{{var6\_eq\_firm = var6 $\times$ eq\_any\_firm}} and
  \texttt{{var7\_eq\_firm = var7 $\times$ eq\_any\_firm}}.

  \item \textbf{{Split design.}}
  Re-estimate the baseline model separately in
  \texttt{{eq\_any\_firm=0}} and \texttt{{eq\_any\_firm=1}} subsamples using
  the same parameterization (\texttt{{var3, var5, var4}} with
  \texttt{{var3,var5}} instrumented by \texttt{{var6,var7}} in IV).

  \item \textbf{{Outcomes kept from defaults.}}
  Firm model reports \texttt{{growth\_rate\_we}}; user model reports
  \texttt{{total\_contributions\_q100}} in the \texttt{{precovid}} panel.
\end{{itemize}}

\subsection*{{Table 1: Firm Scaling (interaction and split)}}
\begin{{table}}[H]
  \centering
  \TableInput{{\cleanedresultsdir/firm_scaling_llm_equity_heterogeneity.tex}}
\end{{table}}

\subsection*{{Table 2: User Productivity (interaction and split)}}
\begin{{table}}[H]
  \centering
  \TableInput{{\cleanedresultsdir/user_productivity_llm_equity_heterogeneity_precovid.tex}}
\end{{table}}

\end{{document}}
"""

    ensure_dir(OUT_TEX.parent)
    OUT_TEX.write_text(content, encoding="utf-8")
    print(f"Wrote {OUT_TEX}")


if __name__ == "__main__":
    main()
