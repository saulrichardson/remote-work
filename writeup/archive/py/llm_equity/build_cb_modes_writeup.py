#!/usr/bin/env python3
"""Build standalone LaTeX writeup for LLM-equity CB matched/backfill analysis."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
PY_DIR = PROJECT_ROOT / "src" / "py"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

from project_paths import RESULTS_CLEANED_TEX, ensure_dir, require_file

REQ_TABLES = [
    RESULTS_CLEANED_TEX / "llm_equity_cb_modes_sample_accounting.tex",
    RESULTS_CLEANED_TEX / "llm_equity_cb_modes_descriptives.tex",
    RESULTS_CLEANED_TEX / "llm_equity_cb_modes_firm_core_pooled.tex",
    RESULTS_CLEANED_TEX / "llm_equity_cb_modes_firm_core_split_non_equity.tex",
    RESULTS_CLEANED_TEX / "llm_equity_cb_modes_firm_core_split_equity.tex",
    RESULTS_CLEANED_TEX / "llm_equity_cb_modes_firm_intensive_share.tex",
    RESULTS_CLEANED_TEX / "llm_equity_cb_modes_firm_intensive_count_mean.tex",
    RESULTS_CLEANED_TEX / "llm_equity_cb_modes_firm_reduced1.tex",
    RESULTS_CLEANED_TEX / "llm_equity_cb_modes_firm_simple_dd.tex",
    RESULTS_CLEANED_TEX / "llm_equity_cb_modes_firm_concentration_any.tex",
    RESULTS_CLEANED_TEX / "llm_equity_cb_modes_firm_concentration_share.tex",
    RESULTS_CLEANED_TEX / "llm_equity_cb_modes_firm_concentration_count_mean.tex",
    RESULTS_CLEANED_TEX / "llm_equity_cb_modes_user_core_pooled.tex",
    RESULTS_CLEANED_TEX / "llm_equity_cb_modes_user_core_split_non_equity.tex",
    RESULTS_CLEANED_TEX / "llm_equity_cb_modes_user_core_split_equity.tex",
    RESULTS_CLEANED_TEX / "llm_equity_cb_modes_user_intensive_share.tex",
    RESULTS_CLEANED_TEX / "llm_equity_cb_modes_user_intensive_count_mean.tex",
    RESULTS_CLEANED_TEX / "llm_equity_cb_modes_user_reduced1.tex",
    RESULTS_CLEANED_TEX / "llm_equity_cb_modes_user_simple_dd.tex",
    RESULTS_CLEANED_TEX / "llm_equity_cb_modes_user_concentration_any.tex",
    RESULTS_CLEANED_TEX / "llm_equity_cb_modes_user_concentration_share.tex",
    RESULTS_CLEANED_TEX / "llm_equity_cb_modes_user_concentration_count_mean.tex",
]

OUT_TEX = PROJECT_ROOT / "writeup" / "tex" / "llm_equity_cb_modes_note.tex"


def main() -> None:
    for p in REQ_TABLES:
        require_file(p, nonempty=True, purpose=f"required CB-modes table ({p.name})")

    content = r"""\documentclass{article}
\usepackage[margin=1.0in]{geometry}
\usepackage{booktabs}
\usepackage{makecell}
\usepackage{float}
\usepackage{amsmath,amssymb,amsfonts}
\usepackage{dsfont}
\usepackage[normalem]{ulem}
\usepackage{setspace}
\setstretch{1.05}

\newcommand{\cleanedresultsdir}{../../results/cleaned/tex}
\newcommand{\TableInput}[2][\linewidth]{\input{#2}}

\begin{document}

\section*{LLM Equity Analysis v2: CB-Eligible Matched vs Backfill Modes}

\subsection*{High-level design}
This note estimates equity-compensation heterogeneity using the same core econometric setup as the baseline firm and user specifications. We keep all regression columns in the output (including degenerate zero columns when identification fails in thin matched cells), and we separate two sample-construction modes:
\begin{enumerate}
  \item \textbf{Matched mode:} keep CB-eligible firm$\times$half-year rows with parsed LLM coverage (\texttt{llm\_n\_parse\_ok>0}).
  \item \textbf{Backfill mode:} keep the full CB-eligible universe and set missing equity signal to zero.
\end{enumerate}
Both modes are restricted to the Crunchbase-eligible universe (\texttt{org\_uuid} non-missing in \texttt{firm\_panel\_with\_cb.csv}).

\subsection*{How sample size was limited}
\begin{itemize}
  \item \textbf{Posting universe:} start from postings with non-empty free-text descriptions.
  \item \textbf{Deterministic pre-filter:} restrict to postings with equity-related language (title/description regex triggers) before LLM submission; this is the cost-control and relevance screen.
  \item \textbf{LLM parse screen:} define \texttt{parse ok} as a response that returns output text that can be parsed as valid JSON extraction output.
  \item \textbf{Panel alignment:} aggregate to firm$\times$half-year and merge into baseline outcome panels, then apply CB-eligibility.
\end{itemize}

\subsection*{Merge and construction}
\begin{itemize}
  \item \textbf{LLM aggregation:} posting-level model outputs are aggregated to firm$\times$half-year, yielding \texttt{llm\_equity\_any}, \texttt{llm\_equity\_share\_parse\_ok}, and \texttt{llm\_n\_equity\_true}.
  \item \textbf{Eligibility merge:} CB eligibility is merged via normalized \texttt{companyname}$\times$\texttt{yh} keys and mapped onto the analysis panels.
  \item \textbf{Extensive margin:} \texttt{eq\_any\_firm = max(eq\_any\_obs)} within firm.
  \item \textbf{Intensive margins:}
    \begin{itemize}
      \item \texttt{eq\_share\_firm = mean(eq\_share\_obs)} within firm
      \item \texttt{eq\_count\_mean\_firm = mean(eq\_count\_obs)} within firm
    \end{itemize}
  \item \textbf{Startup split:} startup is age $\leq 10$; non-startup is age $>10$.
\end{itemize}

\subsection*{Measure dictionary: temporal vs non-temporal}
\begin{itemize}
  \item \textbf{Temporal-status convention used in this note:} ``temporal'' means the variable is indexed at firm$\times$half-year (or user$\times$firm$\times$half-year) and can vary over half-years; ``non-temporal'' means a firm-level collapsed measure that is constant over time within firm in the regressions.
\end{itemize}

\paragraph{Sample-construction measures}
\begin{itemize}
  \item \texttt{cb\_eligible}: equals 1 if \texttt{org\_uuid} is observed in \texttt{firm\_panel\_with\_cb.csv} on firm-name$\times$half-year key. \textbf{Temporal} at construction (firm$\times$half-year eligibility flag).
  \item \texttt{llm\_n\_parse\_ok}: count of submitted postings in a firm$\times$half-year cell with parseable JSON extraction output. \textbf{Temporal.}
  \item \texttt{eq\_has\_parse}: indicator \texttt{1[llm\_n\_parse\_ok>0]}. \textbf{Temporal.}
\end{itemize}

\paragraph{LLM equity measures at firm$\times$half-year (temporal)}
\begin{itemize}
  \item \texttt{llm\_equity\_any}: indicator that at least one parsed posting in the cell is equity-positive.
  \item \texttt{llm\_equity\_share\_parse\_ok}: share of parse-ok postings in the cell that are equity-positive.
  \item \texttt{llm\_n\_equity\_true}: count of parse-ok postings in the cell that are equity-positive.
  \item Mode-specific analysis inputs are \texttt{eq\_any\_obs}, \texttt{eq\_share\_obs}, \texttt{eq\_count\_obs}: in matched mode they equal the parsed-cell measures; in backfill mode they equal parsed-cell measures when available and 0 when not parsed.
\end{itemize}

\paragraph{Firm-level equity measures used for heterogeneity (non-temporal)}
\begin{itemize}
  \item \texttt{eq\_any\_firm = max(eq\_any\_obs)} within firm.
  \item \texttt{eq\_share\_firm = mean(eq\_share\_obs)} within firm.
  \item \texttt{eq\_count\_mean\_firm = mean(eq\_count\_obs)} within firm.
  \item These are firm-level collapsed objects and therefore \textbf{non-temporal} in the regressions.
\end{itemize}

\paragraph{Regression terms and outcomes}
\begin{itemize}
  \item \textbf{Core treatment terms (temporal):} Remote$\times$Post, Remote$\times$Post$\times$Startup, and Startup$\times$Post (implemented as \texttt{var3}, \texttt{var5}, \texttt{var4}).
  \item \textbf{IV instruments (temporal):} Teleworkable$\times$Post and Teleworkable$\times$Post$\times$Startup (implemented as \texttt{var6}, \texttt{var7}).
  \item \textbf{Equity interactions (temporal):} interactions with Post and Remote$\times$Post are temporal because they multiply time-varying post-period terms by the non-temporal firm-level equity measures.
  \item \textbf{Startup status:} \texttt{startup = 1[age <= 10]} and non-startup otherwise; this is defined at firm$\times$half-year and can change over time as firm age increases.
  \item \textbf{Outcomes (temporal):} \texttt{growth\_rate\_we} at firm$\times$half-year and \texttt{total\_contributions\_q100} at user$\times$firm$\times$half-year.
  \item \textbf{Important interpretation for share:} \texttt{eq\_share\_firm} is the average of firm$\times$half-year shares within firm; it is not a single postings-weighted share pooled across all periods.
\end{itemize}

\subsection*{Descriptive evidence}
\begin{table}[H]
  \centering
  \caption{Sample accounting across matched and backfill modes}
  \TableInput{\cleanedresultsdir/llm_equity_cb_modes_sample_accounting.tex}
\end{table}

\begin{table}[H]
  \centering
  \caption{Startup vs non-startup equity prevalence and intensive margins}
  \TableInput{\cleanedresultsdir/llm_equity_cb_modes_descriptives.tex}
\end{table}

\subsection*{Regression evidence: one table per regression}
Each table below corresponds to one regression block. Rows are the classic terms from that exact regression only.

\subsubsection*{Firm growth regressions}
\begin{table}[H]
  \centering
  \caption{Firm growth: core pooled (extensive margin)}
  \TableInput{\cleanedresultsdir/llm_equity_cb_modes_firm_core_pooled.tex}
\end{table}

\begin{table}[H]
  \centering
  \caption{Firm growth: core split (non-equity firms)}
  \TableInput{\cleanedresultsdir/llm_equity_cb_modes_firm_core_split_non_equity.tex}
\end{table}

\begin{table}[H]
  \centering
  \caption{Firm growth: core split (equity firms)}
  \TableInput{\cleanedresultsdir/llm_equity_cb_modes_firm_core_split_equity.tex}
\end{table}

\begin{table}[H]
  \centering
  \caption{Firm growth: intensive margin (equity share)}
  \TableInput{\cleanedresultsdir/llm_equity_cb_modes_firm_intensive_share.tex}
\end{table}

\begin{table}[H]
  \centering
  \caption{Firm growth: intensive margin (equity count mean)}
  \TableInput{\cleanedresultsdir/llm_equity_cb_modes_firm_intensive_count_mean.tex}
\end{table}

\begin{table}[H]
  \centering
  \caption{Firm growth: reduced-1 (Remote DD + equity heterogeneity; no startup interaction)}
  \TableInput{\cleanedresultsdir/llm_equity_cb_modes_firm_reduced1.tex}
\end{table}

\begin{table}[H]
  \centering
  \caption{Firm growth: reduced-2 (Remote $\times$ Post only DD)}
  \TableInput{\cleanedresultsdir/llm_equity_cb_modes_firm_simple_dd.tex}
\end{table}

\begin{table}[H]
  \centering
  \caption{Firm growth: concentration OLS (equity exposure $\times$ post, extensive margin)}
  \TableInput{\cleanedresultsdir/llm_equity_cb_modes_firm_concentration_any.tex}
\end{table}

\begin{table}[H]
  \centering
  \caption{Firm growth: concentration OLS (equity exposure $\times$ post, share intensity)}
  \TableInput{\cleanedresultsdir/llm_equity_cb_modes_firm_concentration_share.tex}
\end{table}

\begin{table}[H]
  \centering
  \caption{Firm growth: concentration OLS (equity exposure $\times$ post, count intensity)}
  \TableInput{\cleanedresultsdir/llm_equity_cb_modes_firm_concentration_count_mean.tex}
\end{table}

\subsubsection*{User productivity regressions}
\begin{table}[H]
  \centering
  \caption{User productivity: core pooled (extensive margin)}
  \TableInput{\cleanedresultsdir/llm_equity_cb_modes_user_core_pooled.tex}
\end{table}

\begin{table}[H]
  \centering
  \caption{User productivity: core split (non-equity firms)}
  \TableInput{\cleanedresultsdir/llm_equity_cb_modes_user_core_split_non_equity.tex}
\end{table}

\begin{table}[H]
  \centering
  \caption{User productivity: core split (equity firms)}
  \TableInput{\cleanedresultsdir/llm_equity_cb_modes_user_core_split_equity.tex}
\end{table}

\begin{table}[H]
  \centering
  \caption{User productivity: intensive margin (equity share)}
  \TableInput{\cleanedresultsdir/llm_equity_cb_modes_user_intensive_share.tex}
\end{table}

\begin{table}[H]
  \centering
  \caption{User productivity: intensive margin (equity count mean)}
  \TableInput{\cleanedresultsdir/llm_equity_cb_modes_user_intensive_count_mean.tex}
\end{table}

\begin{table}[H]
  \centering
  \caption{User productivity: reduced-1 (Remote DD + equity heterogeneity; no startup interaction)}
  \TableInput{\cleanedresultsdir/llm_equity_cb_modes_user_reduced1.tex}
\end{table}

\begin{table}[H]
  \centering
  \caption{User productivity: reduced-2 (Remote $\times$ Post only DD)}
  \TableInput{\cleanedresultsdir/llm_equity_cb_modes_user_simple_dd.tex}
\end{table}

\begin{table}[H]
  \centering
  \caption{User productivity: concentration OLS (equity exposure $\times$ post, extensive margin)}
  \TableInput{\cleanedresultsdir/llm_equity_cb_modes_user_concentration_any.tex}
\end{table}

\begin{table}[H]
  \centering
  \caption{User productivity: concentration OLS (equity exposure $\times$ post, share intensity)}
  \TableInput{\cleanedresultsdir/llm_equity_cb_modes_user_concentration_share.tex}
\end{table}

\begin{table}[H]
  \centering
  \caption{User productivity: concentration OLS (equity exposure $\times$ post, count intensity)}
  \TableInput{\cleanedresultsdir/llm_equity_cb_modes_user_concentration_count_mean.tex}
\end{table}

\subsection*{Interpretation and caveats}
\begin{itemize}
  \item \textbf{Semantic meaning of backfill:} backfill does \emph{not} mean ``the firm truly did not offer equity'' in unparsed cells. It means ``no observed equity signal in the submitted/parsed candidate pipeline'' for that firm$\times$half-year.
  \item Backfill mode increases power by coding that unobserved signal as zero in the CB-eligible universe; this is a modeling assumption tied to the candidate-submission pipeline and should be interpreted as such.
  \item Matched mode is the strict observed-signal design and is the conservative reference point for observed equity data.
  \item Count intensity is the firm-level average number of equity-positive postings (\texttt{eq\_count\_mean\_firm}).
  \item \textbf{Reduced-1} is the ``Remote DD + equity heterogeneity'' check without the startup interaction layer.
  \item \textbf{Reduced-2} is the minimum-power remote$\times$post-only DD.
  \item \textbf{Concentration OLS} removes the remote regressor and asks whether post-period changes are concentrated in equity-exposed firms.
\end{itemize}

\end{document}
"""

    ensure_dir(OUT_TEX.parent)
    OUT_TEX.write_text(content, encoding="utf-8")
    print(f"Wrote {OUT_TEX}")


if __name__ == "__main__":
    main()
