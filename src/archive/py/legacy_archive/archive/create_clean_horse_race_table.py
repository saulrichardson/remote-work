import pandas as pd
import numpy as np

# Read the results
df = pd.read_csv('/Users/saul/Dropbox/Remote Work Startups/main/results/raw/scaling_horse_race_clean_precovid/horse_race_clean_results.csv')

# Function to format coefficient with stars
def format_coef(coef, pval):
    stars = ""
    if pval < 0.01:
        stars = "***"
    elif pval < 0.05:
        stars = "**"
    elif pval < 0.1:
        stars = "*"
    return f"{coef:.2f}{stars}"

# Function to format standard error
def format_se(se):
    return f"({se:.2f})"

# Calculate combined effects
results = {}

for spec in ['baseline', 'growth', 'growth_resid', 'rent', 'hhi']:
    for method in ['OLS', 'IV']:
        row = df[(df['specification'] == spec) & (df['method'] == method)].iloc[0]
        
        # For baseline, only low characteristic exists
        if spec == 'baseline':
            # Regular firms - low
            reg_low = row['b3']
            reg_low_se = row['se3']
            reg_low_p = row['p3']
            
            # Startups - low  
            startup_low = row['b3'] + row['b5']
            startup_low_se = np.sqrt(row['se3']**2 + row['se5']**2)  # Approximate
            startup_low_p = row['p5']  # Use startup coefficient p-value
            
            results[(spec, method, 'reg_low')] = (reg_low, reg_low_se, reg_low_p)
            results[(spec, method, 'startup_low')] = (startup_low, startup_low_se, startup_low_p)
            results[(spec, method, 'reg_high')] = (np.nan, np.nan, np.nan)
            results[(spec, method, 'startup_high')] = (np.nan, np.nan, np.nan)
        else:
            # Regular firms - low
            reg_low = row['b3']
            reg_low_se = row['se3']
            reg_low_p = row['p3']
            
            # Regular firms - high
            reg_high = row['b3'] + row['b3_int']
            reg_high_se = np.sqrt(row['se3']**2 + row['se3_int']**2)  # Approximate
            reg_high_p = 2 * (1 - abs(reg_high/reg_high_se))  # Approximate p-value
            
            # Startups - low
            startup_low = row['b3'] + row['b5']
            startup_low_se = np.sqrt(row['se3']**2 + row['se5']**2)  # Approximate
            startup_low_p = row['p5']  # Use startup coefficient p-value
            
            # Startups - high
            startup_high = row['b3'] + row['b5'] + row['b3_int'] + row['b5_int']
            startup_high_se = np.sqrt(row['se3']**2 + row['se5']**2 + row['se3_int']**2 + row['se5_int']**2)  # Approximate
            startup_high_p = 2 * (1 - abs(startup_high/startup_high_se))  # Approximate p-value
            
            results[(spec, method, 'reg_low')] = (reg_low, reg_low_se, reg_low_p)
            results[(spec, method, 'reg_high')] = (reg_high, reg_high_se, reg_high_p)
            results[(spec, method, 'startup_low')] = (startup_low, startup_low_se, startup_low_p)
            results[(spec, method, 'startup_high')] = (startup_high, startup_high_se, startup_high_p)

# Print LaTeX table content
print("% OLS Panel")
print("\\multicolumn{6}{c}{\\textit{Panel A: OLS Estimates}} \\\\")
print("\\midrule")
print("\\multicolumn{6}{l}{\\textit{Remote Effect for Regular Firms:}} \\\\")

# Regular firms - Low characteristic (OLS)
print("Low Characteristic & ", end="")
for spec in ['baseline', 'growth', 'growth_resid', 'rent', 'hhi']:
    coef, se, p = results[(spec, 'OLS', 'reg_low')]
    print(f"${format_coef(coef, p)}$ & ", end="")
print("\\\\")

print("& ", end="")
for spec in ['baseline', 'growth', 'growth_resid', 'rent', 'hhi']:
    coef, se, p = results[(spec, 'OLS', 'reg_low')]
    print(f"{format_se(se)} & ", end="")
print("\\\\")

# Regular firms - High characteristic (OLS)
print("High Characteristic & ", end="")
for spec in ['baseline', 'growth', 'growth_resid', 'rent', 'hhi']:
    coef, se, p = results[(spec, 'OLS', 'reg_high')]
    if np.isnan(coef):
        print("-- & ", end="")
    else:
        print(f"${format_coef(coef, p)}$ & ", end="")
print("\\\\")

print("& ", end="")
for spec in ['baseline', 'growth', 'growth_resid', 'rent', 'hhi']:
    coef, se, p = results[(spec, 'OLS', 'reg_high')]
    if not np.isnan(coef):
        print(f"{format_se(se)} & ", end="")
    else:
        print("& ", end="")
print("\\\\")

print("\\midrule")
print("\\multicolumn{6}{l}{\\textit{Remote Effect for Startups:}} \\\\")

# Startups - Low characteristic (OLS)
print("Low Characteristic & ", end="")
for spec in ['baseline', 'growth', 'growth_resid', 'rent', 'hhi']:
    coef, se, p = results[(spec, 'OLS', 'startup_low')]
    print(f"${format_coef(coef, p)}$ & ", end="")
print("\\\\")

print("& ", end="")
for spec in ['baseline', 'growth', 'growth_resid', 'rent', 'hhi']:
    coef, se, p = results[(spec, 'OLS', 'startup_low')]
    print(f"{format_se(se)} & ", end="")
print("\\\\")

# Startups - High characteristic (OLS)
print("High Characteristic & ", end="")
for spec in ['baseline', 'growth', 'growth_resid', 'rent', 'hhi']:
    coef, se, p = results[(spec, 'OLS', 'startup_high')]
    if np.isnan(coef):
        print("-- & ", end="")
    else:
        print(f"${format_coef(coef, p)}$ & ", end="")
print("\\\\")

print("& ", end="")
for spec in ['baseline', 'growth', 'growth_resid', 'rent', 'hhi']:
    coef, se, p = results[(spec, 'OLS', 'startup_high')]
    if not np.isnan(coef):
        print(f"{format_se(se)} & ", end="")
    else:
        print("& ", end="")
print("\\\\")

print("\\midrule")
print("\\multicolumn{6}{c}{\\textit{Panel B: IV Estimates}} \\\\")
print("\\midrule")
print("\\multicolumn{6}{l}{\\textit{Remote Effect for Regular Firms:}} \\\\")

# Regular firms - Low characteristic (IV)
print("Low Characteristic & ", end="")
for spec in ['baseline', 'growth', 'growth_resid', 'rent', 'hhi']:
    coef, se, p = results[(spec, 'IV', 'reg_low')]
    print(f"${format_coef(coef, p)}$ & ", end="")
print("\\\\")

print("& ", end="")
for spec in ['baseline', 'growth', 'growth_resid', 'rent', 'hhi']:
    coef, se, p = results[(spec, 'IV', 'reg_low')]
    print(f"{format_se(se)} & ", end="")
print("\\\\")

# Regular firms - High characteristic (IV)
print("High Characteristic & ", end="")
for spec in ['baseline', 'growth', 'growth_resid', 'rent', 'hhi']:
    coef, se, p = results[(spec, 'IV', 'reg_high')]
    if np.isnan(coef):
        print("-- & ", end="")
    else:
        print(f"${format_coef(coef, p)}$ & ", end="")
print("\\\\")

print("& ", end="")
for spec in ['baseline', 'growth', 'growth_resid', 'rent', 'hhi']:
    coef, se, p = results[(spec, 'IV', 'reg_high')]
    if not np.isnan(coef):
        print(f"{format_se(se)} & ", end="")
    else:
        print("& ", end="")
print("\\\\")

print("\\midrule")
print("\\multicolumn{6}{l}{\\textit{Remote Effect for Startups:}} \\\\")

# Startups - Low characteristic (IV)
print("Low Characteristic & ", end="")
for spec in ['baseline', 'growth', 'growth_resid', 'rent', 'hhi']:
    coef, se, p = results[(spec, 'IV', 'startup_low')]
    print(f"${format_coef(coef, p)}$ & ", end="")
print("\\\\")

print("& ", end="")
for spec in ['baseline', 'growth', 'growth_resid', 'rent', 'hhi']:
    coef, se, p = results[(spec, 'IV', 'startup_low')]
    print(f"{format_se(se)} & ", end="")
print("\\\\")

# Startups - High characteristic (IV)
print("High Characteristic & ", end="")
for spec in ['baseline', 'growth', 'growth_resid', 'rent', 'hhi']:
    coef, se, p = results[(spec, 'IV', 'startup_high')]
    if np.isnan(coef):
        print("-- & ", end="")
    else:
        print(f"${format_coef(coef, p)}$ & ", end="")
print("\\\\")

print("& ", end="")
for spec in ['baseline', 'growth', 'growth_resid', 'rent', 'hhi']:
    coef, se, p = results[(spec, 'IV', 'startup_high')]
    if not np.isnan(coef):
        print(f"{format_se(se)} & ", end="")
    else:
        print("& ", end="")
print("\\\\")