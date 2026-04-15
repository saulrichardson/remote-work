#!/usr/bin/env python3
"""
Check role_k7 categories to see if they're better for composition analysis
"""

import pandas as pd

# Read sample data
df = pd.read_csv(
    '/Users/saul/Dropbox/Remote Work Startups/main/data/raw/Scoop_workers_positions.csv',
    nrows=10000,
    usecols=['role_k7', 'seniority', 'title', 'companyname']
)

# Check role_k7 distribution
print("Role_k7 Distribution:")
print("="*60)
role_counts = df['role_k7'].value_counts()
print(role_counts)
print(f"\nTotal unique roles: {len(role_counts)}")

# Check coverage
coverage = df['role_k7'].notna().sum() / len(df) * 100
print(f"\nCoverage: {coverage:.1f}%")

# Show how roles map to seniority
print("\n\nRole × Seniority Distribution:")
print("="*60)
crosstab = pd.crosstab(df['role_k7'], df['seniority'], normalize='columns') * 100
print(crosstab.round(1))

# Show sample titles for each role
print("\n\nSample job titles by role_k7:")
print("="*60)
for role in role_counts.head(7).index:
    if pd.notna(role):
        print(f"\n{role}:")
        sample_titles = df[df['role_k7'] == role]['title'].value_counts().head(5)
        for title, count in sample_titles.items():
            print(f"  - {title} ({count})")