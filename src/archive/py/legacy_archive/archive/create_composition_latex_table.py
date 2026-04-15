#!/usr/bin/env python3
"""
Create formatted LaTeX table for composition results
"""

# Read the Stata output
with open('results/raw/scaling_composition_precovid_all.txt', 'r') as f:
    content = f.read()

# Create main paper table
latex_table = r"""\begin{table}[H]
\centering
\caption{Firm Scaling and Pre-COVID Workforce Composition}
\label{tab:scaling_composition}
\scriptsize
\begin{adjustbox}{max width=\linewidth}
\begin{tabular}{lcccccc}
\toprule
 & \multicolumn{4}{c}{Role Composition} & \multicolumn{2}{c}{Seniority} \\
\cmidrule(lr){2-5} \cmidrule(lr){6-7}
 & (1) & (2) & (3) & (4) & (5) & (6) \\
 & Baseline & Sales & Marketing & Scientist & Entry & Mid/Senior \\
\midrule
Startup & 0.070*** & 0.050*** & 0.087*** & 0.066*** & 0.067*** & 0.101*** \\
 & (0.004) & (0.008) & (0.006) & (0.004) & (0.007) & (0.013) \\
[0.5ex]
Composition share & & -0.000*** & 0.000* & 0.000 & -0.001*** & 0.001*** \\
 & & (0.000) & (0.000) & (0.000) & (0.000) & (0.000) \\
[0.5ex]
Startup $\times$ Composition & & 0.001*** & -0.001*** & 0.001** & -0.000 & -0.001*** \\
 & & (0.000) & (0.000) & (0.000) & (0.000) & (0.000) \\
\midrule
Controls & Yes & Yes & Yes & Yes & Yes & Yes \\
Observations & 15,284 & 15,284 & 15,284 & 15,284 & 15,284 & 15,284 \\
R-squared & 0.117 & 0.119 & 0.119 & 0.118 & 0.129 & 0.122 \\
\bottomrule
\end{tabular}
\end{adjustbox}
\begin{tablenotes}[flushleft]
\scriptsize
\item \textit{Notes:} This table examines how pre-COVID (2019) workforce composition affects firm growth during COVID. The dependent variable is employment growth rate (winsorized). Composition shares are measured as percentages (0-100) of the firm's 2019 workforce. All specifications include controls for firm age, rent costs, market concentration (HHI), and year-half fixed effects. Robust standard errors in parentheses. *** p$<$0.01, ** p$<$0.05, * p$<$0.10.
\end{tablenotes}
\end{table}"""

# Save the main table
with open('results/cleaned/scaling_composition_precovid.tex', 'w') as f:
    f.write(latex_table)

# Create summary statistics table
summary_table = r"""\begin{table}[H]
\centering
\caption{Summary of Composition Effects on Startup Scaling}
\label{tab:composition_summary}
\small
\begin{tabular}{lcc}
\toprule
\textbf{Workforce Characteristic} & \textbf{Interaction Effect} & \textbf{Interpretation} \\
\midrule
\multicolumn{3}{l}{\textit{Role Composition}} \\
Sales share & 0.001*** & More sales staff helps startups scale \\
Marketing share & -0.001*** & More marketing staff hurts startup scaling \\
Scientist share & 0.001** & Technical/R\&D focus helps startups scale \\
Engineer share & -0.000 & No differential effect for startups \\
\midrule
\multicolumn{3}{l}{\textit{Seniority Composition}} \\
Entry level (L1) & -0.000 & No differential effect \\
Mid/Senior ICs (L2) & -0.001*** & Too many mid-level staff hurts scaling \\
Managers (L3) & 0.000 & No differential effect \\
Directors+ (L4) & 0.000 & No differential effect \\
\bottomrule
\end{tabular}
\end{table}"""

with open('results/cleaned/scaling_composition_summary.tex', 'w') as f:
    f.write(summary_table)

print("LaTeX tables created:")
print("- results/cleaned/scaling_composition_precovid.tex")
print("- results/cleaned/scaling_composition_summary.tex")