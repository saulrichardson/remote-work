#!/usr/bin/env python3
"""Build a standalone LaTeX tech note for the LLM-equity results.

Design goal (per PI requests):
  - Table-by-table write-up.
  - An explicit empirical-spec equation block before each regression table.
  - Per-table Notes that explain how to read columns/rows and how to combine coefficients.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
PY_DIR = PROJECT_ROOT / "src" / "py"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

from project_paths import RESULTS_CLEANED_TEX, ensure_dir, require_file

REQ_TABLES: Final[list[Path]] = [
    # Anchor descriptives (from no-CB backfill universe)
    RESULTS_CLEANED_TEX / "llm_equity_pi_followups_anchor_sample.tex",
    RESULTS_CLEANED_TEX / "llm_equity_pi_followups_anchor_descriptives.tex",
    # Core equity heterogeneity (backfill)
    RESULTS_CLEANED_TEX / "firm_scaling_llm_equity_heterogeneity.tex",
    RESULTS_CLEANED_TEX / "user_productivity_llm_equity_heterogeneity_precovid.tex",
    # Replace startup with equity (reduced DD)
    RESULTS_CLEANED_TEX / "llm_equity_pi_followups_reduced1_firm.tex",
    RESULTS_CLEANED_TEX / "llm_equity_pi_followups_reduced1_user.tex",
    # Equity as mechanism (baseline spec + equity controls)
    RESULTS_CLEANED_TEX / "llm_equity_mechanism_variants_firm.tex",
    RESULTS_CLEANED_TEX / "llm_equity_mechanism_variants_user.tex",
    # Robustness checks / horse races
    RESULTS_CLEANED_TEX / "llm_equity_pi_followups_pair_fe_quick.tex",
    RESULTS_CLEANED_TEX / "llm_equity_pi_followups_horse_race.tex",
    # Automated scan summary (equity terms with p<0.10)
    RESULTS_CLEANED_TEX / "llm_equity_significance_scan.tex",
]

OUT_TEX: Final[Path] = PROJECT_ROOT / "writeup" / "tex" / "llm_equity_tech_status_note.tex"


def main() -> None:
    for path in REQ_TABLES:
        require_file(path, nonempty=True, purpose="required equity-analysis LaTeX table")

    content = r"""\documentclass{article}
\usepackage[margin=1.0in]{geometry}
\usepackage{booktabs}
\usepackage{makecell}
\usepackage{float}
\usepackage{caption}
\usepackage{amsmath,amssymb,amsfonts}
\usepackage{dsfont}
\usepackage[normalem]{ulem}
\usepackage{setspace}
\setstretch{1.05}

\newcommand{\cleanedresultsdir}{../../results/cleaned/tex}
\newcommand{\TableInput}[2][\linewidth]{\input{#2}}
\DeclareCaptionStyle{noteflush}{%
  format=plain,
  justification=raggedright,
  singlelinecheck=false,
  font=footnotesize,
  width=\linewidth,
  skip=0pt
}
\newcommand{\FloatNote}[1]{%
  \begingroup
    \captionsetup{style=noteflush}%
    \caption*{\textit{Notes:}~#1}%
  \endgroup
}

\begin{document}

\section*{LLM Equity: Table-by-Table Specs and Results}

\noindent\textit{Compilation date: \today. All tables are read from \texttt{results/cleaned/tex}.}

\subsection*{Table 1: Anchor sample accounting}
\noindent \textbf{Equity coding rule.} The LLM is run only on postings that hit an equity keyword screen. Postings that do not hit the screen are treated as not offering employee equity compensation, and firm$\times$half-year equity measures are therefore set to 0 in cells with zero keyword-hit postings. Define $\texttt{EquityFirm}_f=1$ if firm $f$ is equity-positive in at least one half-year, and 0 otherwise.
\begin{table}[H]\centering
  \caption{Anchor sample accounting}
  \TableInput{\cleanedresultsdir/llm_equity_pi_followups_anchor_sample.tex}
  \FloatNote{This is a two-column accounting table. The left column lists a \emph{metric} and the right column lists the corresponding \emph{value}. ``Firm$\times$half-year rows'' is the number of firm$\times$half-year observations in the firm panel used for the firm-level regressions in this note (Tables 3, 5, and 7). ``Firms'' is the number of unique firms in that panel. ``Startup firms'' and ``Non-startup firms'' split the unique-firm count by the baseline startup indicator (startup is defined as firm age $\leq 10$ as of 2020 in the baseline firm panel). ``Firms with any equity signal'' counts unique firms with $\texttt{EquityFirm}_f=1$ under the coding rule stated above.}
\end{table}

\subsection*{Table 2: Equity prevalence + intensive margins}
\noindent Define two firm-level intensive-margin summaries from the firm$\times$half-year LLM panel. Let $\texttt{EquityShare}_{fh}$ denote the share of keyword-hit postings in firm $f$, half-year $h$ that the LLM classifies as offering employee equity compensation; let $\texttt{EquityCount}_{fh}$ denote the corresponding count. When a firm$\times$half-year has zero keyword-hit postings, set $\texttt{EquityShare}_{fh}=0$ and $\texttt{EquityCount}_{fh}=0$. Then define firm-level averages:
\[
  \texttt{EquityShareFirm}_f \equiv \frac{1}{H_f}\sum_h \texttt{EquityShare}_{fh},
  \qquad
  \texttt{EquityCountMeanFirm}_f \equiv \frac{1}{H_f}\sum_h \texttt{EquityCount}_{fh},
\]
where $H_f$ is the number of half-year cells observed for firm $f$ in the firm panel.
\begin{table}[H]\centering
  \caption{Anchor descriptives}
  \TableInput{\cleanedresultsdir/llm_equity_pi_followups_anchor_descriptives.tex}
  \FloatNote{Rows split firms into Startups vs Non-startups (startup defined as firm age $\leq 10$ as of 2020). ``Firms'' is the number of unique firms in the group. ``\% any equity'' is the share of firms in the group with $\texttt{EquityFirm}_f=1$. ``Mean share'' / ``Median share'' summarize $\texttt{EquityShareFirm}_f$; ``Mean count'' / ``Median count'' summarize $\texttt{EquityCountMeanFirm}_f$. These are unconditional firm-level moments under the coding rule described in Table 1.}
\end{table}

\subsection*{Table 3: Firm scaling (growth) --- equity heterogeneity}
\noindent \textbf{Specification (pooled interaction).}
\begin{equation*}
\begin{aligned}
  y_{fh} ={}&
  \beta_3\,(\texttt{remote}_f\times \mathds{1}(\text{Post})_h)
  + \beta_5\,(\texttt{remote}_f\times \texttt{startup}_f\times \mathds{1}(\text{Post})_h) \\
  &+ \beta_{3e}\,(\texttt{remote}_f\times \mathds{1}(\text{Post})_h\times \texttt{EquityFirm}_f)
  + \beta_{5e}\,(\texttt{remote}_f\times \texttt{startup}_f\times \mathds{1}(\text{Post})_h\times \texttt{EquityFirm}_f) \\
  &+ \beta_{eP}\,(\texttt{EquityFirm}_f\times \mathds{1}(\text{Post})_h)
  + \gamma\,(\texttt{startup}_f\times \mathds{1}(\text{Post})_h)
  + \alpha_f + \tau_h + \varepsilon_{fh}.
\end{aligned}
\end{equation*}
\noindent \textbf{2SLS.} Instrument the two remote terms by replacing $\texttt{remote}_f$ with $\texttt{teleworkable}_f$ in the corresponding interactions, and apply the same $\texttt{EquityFirm}_f$ interactions to the instruments. Absorb firm and half-year fixed effects and cluster standard errors by firm.

\medskip
\noindent \textbf{Specification (split baseline).}
Re-estimate the baseline model separately for $\texttt{EquityFirm}_f\in\{0,1\}$:
\begin{equation*}
  y_{fh} =
  \beta_3\,(\texttt{remote}_f\times \mathds{1}(\text{Post})_h)
  + \beta_5\,(\texttt{remote}_f\times \texttt{startup}_f\times \mathds{1}(\text{Post})_h)
  + \gamma\,(\texttt{startup}_f\times \mathds{1}(\text{Post})_h)
  + \alpha_f + \tau_h + \varepsilon_{fh}.
\end{equation*}
\begin{table}[H]\centering
  \caption{Firm scaling: pooled interaction + split baseline}
  \TableInput{\cleanedresultsdir/firm_scaling_llm_equity_heterogeneity.tex}
  \FloatNote{Outcome is firm growth rate at the firm$\times$half-year level. Columns (1)--(2) (``Pooled'') report OLS and IV for the pooled interaction specification; columns (3)--(6) (``Non-equity'' / ``Equity'') re-estimate the \emph{baseline} model separately on the $\texttt{EquityFirm}_f=0$ and $\texttt{EquityFirm}_f=1$ subsamples. In the pooled columns, the row $\texttt{Remote}\times\mathds{1}(\text{Post})$ is $\beta_3$ (post remote effect for non-startups in non-equity firms), and the row $\texttt{Remote}\times\mathds{1}(\text{Post})\times\text{Startup}$ is $\beta_5$ (incremental post remote effect for startups in non-equity firms). The equity-heterogeneity rows are incremental differences for equity firms: $\beta_{3e}$ on $\texttt{Remote}\times\mathds{1}(\text{Post})\times\text{EquityFirm}$ and $\beta_{5e}$ on $\texttt{Remote}\times\mathds{1}(\text{Post})\times\text{Startup}\times\text{EquityFirm}$. To read group-specific post remote effects in the pooled columns: non-startup/non-equity is $\beta_3$; startup/non-equity is $\beta_3+\beta_5$; non-startup/equity is $\beta_3+\beta_{3e}$; startup/equity is $\beta_3+\beta_5+\beta_{3e}+\beta_{5e}$. The row $\texttt{EquityFirm}\times\mathds{1}(\text{Post})$ is an additional post-period shift for equity firms holding remote exposure and startup status fixed. ``KP rk Wald F'' reports the Kleibergen--Paap rk Wald F statistic (IV columns only). Standard errors are clustered by firm and reported in parentheses; *, **, *** denote $p<0.10, 0.05, 0.01$.}
\end{table}

\subsection*{Table 4: User productivity --- equity heterogeneity}
\noindent \textbf{Specification (pooled interaction).}
\begin{equation*}
\begin{aligned}
  y_{ifh} ={}&
  \beta_3\,(\texttt{remote}_f\times \mathds{1}(\text{Post})_h)
  + \beta_5\,(\texttt{remote}_f\times \texttt{startup}_f\times \mathds{1}(\text{Post})_h) \\
  &+ \beta_{3e}\,(\texttt{remote}_f\times \mathds{1}(\text{Post})_h\times \texttt{EquityFirm}_f)
  + \beta_{5e}\,(\texttt{remote}_f\times \texttt{startup}_f\times \mathds{1}(\text{Post})_h\times \texttt{EquityFirm}_f) \\
  &+ \beta_{eP}\,(\texttt{EquityFirm}_f\times \mathds{1}(\text{Post})_h)
  + \gamma\,(\texttt{startup}_f\times \mathds{1}(\text{Post})_h)
  + \alpha_i + \alpha_f + \tau_h + \varepsilon_{ifh}.
\end{aligned}
\end{equation*}
absorbing individual, firm, and half-year fixed effects and clustering by worker. The IV instruments the remote interaction terms with the corresponding teleworkability interaction counterparts.
\begin{table}[H]\centering
  \caption{User productivity: pooled interaction + split baseline}
  \TableInput{\cleanedresultsdir/user_productivity_llm_equity_heterogeneity_precovid.tex}
  \FloatNote{Outcome is contribution rank (percentile) at the user$\times$half-year level. Column structure matches Table 3: pooled interaction model in columns (1)--(2) and split baseline model in columns (3)--(6). Rows correspond to the labeled interaction terms. In pooled columns, compute group-specific post remote effects by adding coefficients exactly as in Table 3 (e.g., startup/equity uses $\beta_3+\beta_5+\beta_{3e}+\beta_{5e}$). In split columns, the post remote effect for non-startups is the coefficient on $\texttt{Remote}\times\mathds{1}(\text{Post})$ and for startups is the sum of that coefficient plus the $\texttt{Remote}\times\mathds{1}(\text{Post})\times\text{Startup}$ coefficient. ``KP rk Wald F'' is the Kleibergen--Paap rk Wald F statistic in IV columns. Standard errors are clustered by worker and reported in parentheses; *, **, *** denote $p<0.10, 0.05, 0.01$.}
\end{table}

\subsection*{Table 5: Firm scaling (growth) --- replace startup with equity}
\noindent \textbf{Specification.} This reduced-form variant removes the startup interaction layer and uses only equity heterogeneity:
\begin{equation*}
\begin{aligned}
  y_{fh} ={}&
  \beta_3\,(\texttt{remote}_f\times \mathds{1}(\text{Post})_h)
  + \beta_{3e}\,(\texttt{remote}_f\times \mathds{1}(\text{Post})_h\times \texttt{EquityFirm}_f) \\
  &+ \beta_{eP}\,(\texttt{EquityFirm}_f\times \mathds{1}(\text{Post})_h)
  + \alpha_f + \tau_h + \varepsilon_{fh}.
\end{aligned}
\end{equation*}
\noindent \textbf{2SLS.} Instrument the remote term by replacing $\texttt{remote}_f$ with $\texttt{teleworkable}_f$ in $\texttt{remote}_f\times \mathds{1}(\text{Post})_h$, and apply the same $\texttt{EquityFirm}_f$ interaction to the instrument. Absorb firm and half-year fixed effects and cluster by firm.
\begin{table}[H]\centering
  \caption{Firm scaling: replace startup with equity}
  \TableInput{\cleanedresultsdir/llm_equity_pi_followups_reduced1_firm.tex}
  \FloatNote{Columns report OLS and IV estimates of the reduced-form specification above. The row $\texttt{Remote}\times\mathds{1}(\text{Post})$ is the post remote effect for non-equity firms ($\texttt{EquityFirm}=0$). The interaction row $\texttt{Remote}\times\mathds{1}(\text{Post})\times\texttt{EquityFirm}$ is the \emph{incremental} post remote effect for equity firms relative to non-equity firms. Therefore, the post remote effect for equity firms is the sum of the first two rows. The row $\texttt{EquityFirm}\times\mathds{1}(\text{Post})$ is an additional post-period level shift for equity firms holding remote exposure fixed. ``KP rk Wald F'' is the Kleibergen--Paap rk Wald F statistic (IV only). Standard errors are clustered by firm and reported in parentheses; *, **, *** denote $p<0.10, 0.05, 0.01$.}
\end{table}

\subsection*{Table 6: User productivity --- replace startup with equity}
\noindent \textbf{Specification.}
\begin{equation*}
\begin{aligned}
  y_{ifh} ={}&
  \beta_3\,(\texttt{remote}_f\times \mathds{1}(\text{Post})_h)
  + \beta_{3e}\,(\texttt{remote}_f\times \mathds{1}(\text{Post})_h\times \texttt{EquityFirm}_f) \\
  &+ \beta_{eP}\,(\texttt{EquityFirm}_f\times \mathds{1}(\text{Post})_h)
  + \alpha_i + \alpha_f + \tau_h + \varepsilon_{ifh}.
\end{aligned}
\end{equation*}
absorbing individual, firm, and half-year fixed effects and clustering by worker; IV instruments the remote terms with teleworkability interaction counterparts.
\begin{table}[H]\centering
  \caption{User productivity: replace startup with equity}
  \TableInput{\cleanedresultsdir/llm_equity_pi_followups_reduced1_user.tex}
  \FloatNote{Column and row interpretation matches Table 5, but on the user panel. In particular, the post remote effect for equity firms is the sum of the $\texttt{Remote}\times\mathds{1}(\text{Post})$ row and the $\texttt{Remote}\times\mathds{1}(\text{Post})\times\texttt{EquityFirm}$ row. Standard errors are clustered by worker and reported in parentheses; *, **, *** denote $p<0.10, 0.05, 0.01$.}
\end{table}

\subsection*{Table 7: Firm scaling (growth) --- equity as mechanism (baseline spec + equity controls)}
\noindent \textbf{Specification.} Keep the baseline firm scaling design and add an equity-offer control $Z_{fh}$:
\begin{equation*}
\begin{aligned}
  y_{fh} ={}&
  \beta_3\,(\texttt{remote}_f\times \mathds{1}(\text{Post})_h)
  + \beta_5\,(\texttt{remote}_f\times \texttt{startup}_f\times \mathds{1}(\text{Post})_h) \\
  &+ \gamma\,(\texttt{startup}_f\times \mathds{1}(\text{Post})_h)
  + \delta\,Z_{fh}
  + \alpha_f + \tau_h + \varepsilon_{fh}.
\end{aligned}
\end{equation*}
\noindent The only difference across columns is the definition of $Z_{fh}$:
\[
  Z_{fh}\in\left\{\emptyset,\ \texttt{EquityAny}_{fh},\ \texttt{EquityShare}_{fh},\ \texttt{EquityFirm}_f\cdot \mathds{1}(\text{Post})_h\right\},
\]
where $\texttt{EquityAny}_{fh}$ and $\texttt{EquityShare}_{fh}$ are firm$\times$half-year LLM measures constructed from keyword-hit postings. In firm$\times$half-year cells with zero keyword-hit postings, set $\texttt{EquityAny}_{fh}=0$ and $\texttt{EquityShare}_{fh}=0$. Define $\texttt{EquityFirm}_f\equiv\max_h \texttt{EquityAny}_{fh}$.
\begin{table}[H]\centering
  \caption{Firm scaling: equity as mechanism (baseline spec + equity controls)}
  \TableInput{\cleanedresultsdir/llm_equity_mechanism_variants_firm.tex}
  \FloatNote{Rows report the \emph{baseline} remote coefficients $\beta_3$ on $\texttt{Remote}\times\mathds{1}(\text{Post})$ (post remote effect for non-startups) and $\beta_5$ on $\texttt{Remote}\times\mathds{1}(\text{Post})\times\text{Startup}$ (incremental post remote effect for startups). The post remote effect for startups is the sum of the two rows. Columns (1)--(4) differ only by the equity control $Z_{fh}$ (shown via checkmarks in the bottom panel). Because equity enters only as an additive control (not interacted with the remote terms), the meaning of the two reported coefficients is the same across columns; changes across columns reflect how the baseline remote coefficients move when conditioning on equity-offer measures. Panel A reports OLS and Panel B reports IV (instrumenting the remote interaction terms with teleworkability interaction counterparts). Standard errors are clustered by firm and reported in parentheses; *, **, *** denote $p<0.10, 0.05, 0.01$.}
\end{table}

\subsection*{Table 8: User productivity --- equity as mechanism (baseline spec + equity controls)}
\noindent \textbf{Specification.} Keep the baseline user productivity design and add an equity-offer control $Z_{ifh}$:
\begin{equation*}
\begin{aligned}
  y_{ifh} ={}&
  \beta_3\,(\texttt{remote}_f\times \mathds{1}(\text{Post})_h)
  + \beta_5\,(\texttt{remote}_f\times \texttt{startup}_f\times \mathds{1}(\text{Post})_h) \\
  &+ \gamma\,(\texttt{startup}_f\times \mathds{1}(\text{Post})_h)
  + \delta\,Z_{ifh}
  + \alpha_i + \alpha_f + \tau_h + \varepsilon_{ifh}.
\end{aligned}
\end{equation*}
absorbing individual, firm, and half-year fixed effects and clustering by worker. Columns vary $Z_{ifh}$ exactly as in Table 7.
\begin{table}[H]\centering
  \caption{User productivity: equity as mechanism (baseline spec + equity controls)}
  \TableInput{\cleanedresultsdir/llm_equity_mechanism_variants_user.tex}
  \FloatNote{Rows report the baseline remote coefficients $\beta_3$ on $\texttt{Remote}\times\mathds{1}(\text{Post})$ and $\beta_5$ on $\texttt{Remote}\times\mathds{1}(\text{Post})\times\text{Startup}$; the post remote effect for startups is their sum. Columns (1)--(4) differ only by the equity control included (bottom panel checkmarks). Panel A reports OLS and Panel B reports IV (instrumenting the remote interaction terms with teleworkability interaction counterparts). Standard errors are clustered by worker and reported in parentheses; *, **, *** denote $p<0.10, 0.05, 0.01$.}
\end{table}

\subsection*{Table 9: User productivity --- pair FE sensitivity check (baseline spec)}
\noindent \textbf{Specification.} This table is a fixed-effect sensitivity check for the \emph{baseline} user productivity design:
\begin{equation*}
\begin{aligned}
  y_{ifh} ={}&
  \beta_3\,(\texttt{remote}_f\times \mathds{1}(\text{Post})_h)
  + \beta_5\,(\texttt{remote}_f\times \texttt{startup}_f\times \mathds{1}(\text{Post})_h) \\
  &+ \gamma\,(\texttt{startup}_f\times \mathds{1}(\text{Post})_h)
  + \text{FE} + \varepsilon_{ifh}.
\end{aligned}
\end{equation*}
\noindent Columns differ only in the fixed effects (baseline FE vs match FE); IV instruments the remote interaction terms with the corresponding teleworkability interaction counterparts.
\begin{table}[H]\centering
  \caption{Pair FE sensitivity check}
  \TableInput{\cleanedresultsdir/llm_equity_pi_followups_pair_fe_quick.tex}
  \FloatNote{Columns (1)--(2) use the baseline fixed effects $\alpha_i+\alpha_f+\tau_h$ (individual, firm, half-year). Columns (3)--(4) replace individual and firm fixed effects with a firm$\times$individual fixed effect $\alpha_{if}$ plus half-year FE. ``Main remote effect'' corresponds to $\beta_3$ on $\texttt{Remote}\times\mathds{1}(\text{Post})$ (post remote effect for non-startups). ``Main startup effect'' corresponds to $\beta_5$ on $\texttt{Remote}\times\mathds{1}(\text{Post})\times\text{Startup}$ (incremental post remote effect for startups). The post remote effect for startups is the sum of these two rows. Standard errors are clustered by worker and reported in parentheses; *, **, *** denote $p<0.10, 0.05, 0.01$.}
\end{table}

\subsection*{Table 10: User productivity --- mechanisms / control horse race (OLS + IV)}
\noindent \textbf{Specification.}
\begin{equation*}
\begin{aligned}
  y_{ifh} ={}&
  \beta_3\,(\texttt{remote}_f\times \mathds{1}(\text{Post})_h)
  + \beta_5\,(\texttt{remote}_f\times \texttt{startup}_f\times \mathds{1}(\text{Post})_h)
  + \gamma\,(\texttt{startup}_f\times \mathds{1}(\text{Post})_h) \\
  &+ \alpha_{if} + \tau_h + X_{ifh}'\delta + \varepsilon_{ifh},
\end{aligned}
\end{equation*}
where $\alpha_{if}$ is a firm$\times$individual fixed effect and $X_{ifh}$ varies by column.
\begin{table}[H]\centering
  \caption{User productivity horse race (OLS + IV)}
  \TableInput{\cleanedresultsdir/llm_equity_pi_followups_horse_race.tex}
  \FloatNote{Columns correspond to alternative specifications of the baseline user productivity regression under firm$\times$individual fixed effects; checkmarks indicate which additional controls are included in each column (HHI, seniority, firm growth, and/or equity-offer controls). In columns with equity-offer controls, the added terms are $\texttt{EquityFirm}\times\mathds{1}(\text{Post})$ and $\texttt{EquityFirm}\times\mathds{1}(\text{Post})\times\text{Startup}$ (with $\texttt{EquityFirm}$ defined by the coding rule stated in Table 1). Panel A reports OLS and Panel B reports IV (instrumenting the remote interaction terms with teleworkability interaction counterparts). Rows report $\beta_3$ on $\texttt{Remote}\times\mathds{1}(\text{Post})$ (post remote effect for non-startups) and $\beta_5$ on $\texttt{Remote}\times\mathds{1}(\text{Post})\times\text{Startup}$ (incremental post remote effect for startups). The post remote effect for startups is the sum of the two rows. ``KP rk Wald F'' reports the Kleibergen--Paap rk Wald F statistic for the excluded instruments in each IV column. Standard errors are clustered by worker and reported in parentheses; *, **, *** denote $p<0.10, 0.05, 0.01$.}
\end{table}

\subsection*{Table 11: Significance scan (equity terms only)}
\begin{table}[H]\centering
  \caption{Equity-term significance scan ($p<0.10$)}
  \TableInput{\cleanedresultsdir/llm_equity_significance_scan.tex}
  \FloatNote{This table is a mechanical scan of the equity result CSVs for equity-related parameters with $p<0.10$ in the two core outcomes used in this note (firm growth and contribution rank). It lists the specification label (which identifies the originating script/block), the model type (OLS vs IV), the equity-related parameter, and the corresponding coefficient/standard error and $p$-value. It is intended as a bookkeeping summary of where equity terms are statistically significant; it is not a stand-in for the main regression tables (Tables 3--8), and it does not interpret the estimates.}
\end{table}

\end{document}
"""

    ensure_dir(OUT_TEX.parent)
    OUT_TEX.write_text(content, encoding="utf-8")
    print(f"Wrote {OUT_TEX}")


if __name__ == "__main__":
    main()
