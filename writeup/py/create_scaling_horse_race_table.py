#!/usr/bin/env python3
"""Create a formatted LaTeX table for the scaling horse race results.

This script reads the CSV output from user_productivity_scaling_horse_race.do
and formats it as a LaTeX table similar to other heterogeneity tables.
"""

import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "results" / "raw" / "scaling_horse_race_precovid"
CLEANED_DIR = PROJECT_ROOT / "results" / "cleaned"

def stars(p_value):
    """Add significance stars based on p-value."""
    if p_value < 0.01:
        return "***"
    elif p_value < 0.05:
        return "**"
    elif p_value < 0.10:
        return "*"
    else:
        return ""

def format_coef(coef, se, p, decimals=3):
    """Format coefficient with standard error and stars."""
    return f"{coef:.{decimals}f}{stars(p)}\\\\({se:.{decimals}f})"

def create_horse_race_table():
    """Create the main horse race table."""
    
    # Read results
    df = pd.read_csv(RAW_DIR / "horse_race_results.csv")
    
    # Define column labels
    col_labels = {
        "1_baseline": "Baseline",
        "2_post_growth": "Post-COVID\nGrowth", 
        "3_pre_growth": "Pre-COVID\nGrowth",
        "5_rent": "Rent\nInteraction",
        "6_hhi": "HHI\nInteraction"
    }
    
    # Start building the table
    tex_lines = [
        r"\begin{table}[H]",
        r"\centering",
        r"\caption{Remote Work Productivity: Alternative Specifications}",
        r"\label{tab:scaling_horse_race}",
        r"\centering",
        r"\begin{tabular}{l" + "c" * len(col_labels) + "}",
        r"\toprule",
        " & " + " & ".join(f"({i+1})" for i in range(len(col_labels))) + r" \\",
        " & " + " & ".join(col_labels.values()) + r" \\",
        r"\midrule"
    ]
    
    # Add var3 row (Remote × Post)
    var3_row = r"$ \text{Remote} \times \mathds{1}(\text{Post}) $"
    for spec in col_labels.keys():
        row_data = df[df['specification'] == spec].iloc[0]
        var3_row += " & " + format_coef(row_data['b3'], row_data['se3'], row_data['p3'])
    tex_lines.append(var3_row + r" \\[0.5em]")
    
    # Add var5 row (Remote × Post × Startup)
    var5_row = r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $"
    for spec in col_labels.keys():
        row_data = df[df['specification'] == spec].iloc[0]
        var5_row += " & " + format_coef(row_data['b5'], row_data['se5'], row_data['p5'])
    tex_lines.append(var5_row + r" \\[0.5em]")
    
    # Add growth/interaction rows for specifications that have them
    tex_lines.append(r"\midrule")
    
    # Post-COVID growth interaction (from growth_interaction_precovid results)
    growth_row = r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Growth} $"
    for spec in col_labels.keys():
        if spec == "2_post_growth":
            # From growth_interaction results: var3_g = -0.254 (p=0.282)
            growth_row += r" & -0.254\\(0.237)"
        else:
            growth_row += " & "
    tex_lines.append(growth_row + r" \\[0.5em]")
    
    # Startup × Growth interaction
    startup_growth_row = r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} \times \text{Growth} $"
    for spec in col_labels.keys():
        if spec == "2_post_growth":
            # From growth_interaction results: var5_g = 0.025 (p=0.939)
            startup_growth_row += r" & 0.025\\(0.323)"
        else:
            startup_growth_row += " & "
    tex_lines.append(startup_growth_row + r" \\[0.5em]")
    
    # Rent interaction  
    rent_row = r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Rent} $"
    for spec in col_labels.keys():
        if spec == "5_rent":
            # These are the interaction coefficients we'd need from full results
            rent_row += " & --"
        else:
            rent_row += " & "
    tex_lines.append(rent_row + r" \\[0.5em]")
    
    # HHI interaction
    hhi_row = r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{High HHI} $"
    for spec in col_labels.keys():
        if spec == "6_hhi":
            # From the log, we know var3_hhi = -1.34 (p=0.006)
            hhi_row += r" & -1.344***\\(0.485)"
        else:
            hhi_row += " & "
    tex_lines.append(hhi_row + r" \\[0.5em]")
    
    # Startup × HHI interaction
    startup_hhi_row = r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} \times \text{High HHI} $"
    for spec in col_labels.keys():
        if spec == "6_hhi":
            # From the log, we know var5_hhi = 2.26 (p=0.014)
            startup_hhi_row += r" & 2.258**\\(0.920)"
        else:
            startup_hhi_row += " & "
    tex_lines.append(startup_hhi_row + r" \\[0.5em]")
    
    tex_lines.append(r"\midrule")
    
    # Add N and F-stat rows
    n_row = "N"
    for spec in col_labels.keys():
        row_data = df[df['specification'] == spec].iloc[0]
        n_row += f" & {int(row_data['nobs']):,}"
    tex_lines.append(n_row + r" \\")
    
    f_row = "KP rk Wald F"
    for spec in col_labels.keys():
        row_data = df[df['specification'] == spec].iloc[0]
        f_row += f" & {row_data['rkf']:.2f}"
    tex_lines.append(f_row + r" \\")
    
    tex_lines.extend([
        r"\bottomrule",
        r"\end{tabular}",
        r"",
        r"",
        r"\vspace{0.5em}",
        r"\footnotesize",
        r"\textit{Notes:} This table presents IV estimates of remote work's impact on worker productivity under alternative specifications. ",
        r"Column (1) is the baseline specification. Column (2) interacts treatment with endogenous (post-COVID) firm growth. ",
        r"Column (3) uses exogenous (pre-COVID) growth. Columns (4) and (5) test interactions with rent and labor market concentration (HHI). ",
        r"All specifications include user$\times$firm and half-year fixed effects. Standard errors clustered at the user level.",
        r"*** p$<$0.01, ** p$<$0.05, * p$<$0.1",
        r"\end{table}"
    ])
    
    # Write to file
    output_path = CLEANED_DIR / "scaling_horse_race.tex"
    with open(output_path, 'w') as f:
        f.write('\n'.join(tex_lines))
    
    print(f"✓ Created {output_path}")

def create_growth_predictors_table():
    """Create the growth predictors regression table."""
    
    # Read the outreg2 output if it exists
    tex_path = RAW_DIR / "growth_predictors.tex"
    if tex_path.exists():
        # Just copy it to cleaned directory
        import shutil
        shutil.copy(tex_path, CLEANED_DIR / "growth_predictors.tex")
        print(f"✓ Copied growth predictors table")
    else:
        print(f"✗ Growth predictors table not found at {tex_path}")

if __name__ == "__main__":
    create_horse_race_table()
    create_growth_predictors_table()