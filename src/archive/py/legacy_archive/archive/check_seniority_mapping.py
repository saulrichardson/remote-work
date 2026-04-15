#!/usr/bin/env python3
"""
Check seniority mapping by looking at job titles
"""

import pandas as pd

# Read sample data
df = pd.read_csv(
    '/Users/saul/Dropbox/Remote Work Startups/main/data/raw/Scoop_workers_positions.csv',
    nrows=5000,
    usecols=['title', 'seniority', 'soc_2010', 'company_priname']
)

# Group by seniority and show sample titles
print("Seniority levels and sample job titles:")
print("="*60)

for seniority_level in sorted(df['seniority'].unique()):
    if pd.notna(seniority_level):
        sample_titles = df[df['seniority'] == seniority_level]['title'].value_counts().head(10)
        print(f"\nSeniority Level {int(seniority_level)}:")
        for title, count in sample_titles.items():
            print(f"  - {title} ({count})")

# Also check if there's a pattern in the data
print("\n\nChecking for seniority patterns in titles:")
print("="*60)

# Common seniority keywords
keywords = {
    'junior': ['junior', 'jr', 'entry', 'associate'],
    'senior': ['senior', 'sr', 'lead', 'principal'],
    'manager': ['manager', 'mgr', 'supervisor'],
    'director': ['director', 'vp', 'vice president'],
    'executive': ['chief', 'ceo', 'cfo', 'cto', 'president', 'owner']
}

for level in [1, 2, 3, 4]:
    print(f"\nLevel {level} title patterns:")
    level_titles = df[df['seniority'] == level]['title'].fillna('').str.lower()
    for category, words in keywords.items():
        matches = sum(any(word in title for word in words) for title in level_titles)
        pct = matches / len(level_titles) * 100 if len(level_titles) > 0 else 0
        print(f"  {category}: {pct:.1f}%")