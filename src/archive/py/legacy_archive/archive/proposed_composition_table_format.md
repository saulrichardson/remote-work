# Proposed Table Format for Composition Results

## Data Structure from CSVs:

### scaling_composition_roles.csv contains:
- role (Admin, Engineer, Finance, Marketing, Operations, Sales, Scientist)
- model_type (OLS, IV)
- param (var3, var5, var4)
- coef, se, pval, pre_mean, nobs, rkf

### scaling_composition_seniority.csv contains:
- seniority (Level_1, Level_2, Level_3, Level_4)
- model_type (OLS, IV)
- param (var3, var5, var4)
- coef, se, pval, pre_mean, nobs, rkf

## Proposed Table 1: Role Composition Effects on Firm Scaling

```
                          (1)         (2)         (3)         (4)         (5)         (6)         (7)
                       Baseline     Admin    Engineer    Finance   Marketing  Operations    Sales
------------------------------------------------------------------------------------------------------
Panel A: OLS
Remote × Post          [var3]      [var3]      [var3]      [var3]      [var3]      [var3]      [var3]
                       (se)        (se)        (se)        (se)        (se)        (se)        (se)

Remote × Post × Startup [var5]      [var5]      [var5]      [var5]      [var5]      [var5]      [var5]
                       (se)        (se)        (se)        (se)        (se)        (se)        (se)

Panel B: IV  
Remote × Post          [var3]      [var3]      [var3]      [var3]      [var3]      [var3]      [var3]
                       (se)        (se)        (se)        (se)        (se)        (se)        (se)

Remote × Post × Startup [var5]      [var5]      [var5]      [var5]      [var5]      [var5]      [var5]
                       (se)        (se)        (se)        (se)        (se)        (se)        (se)

N                      [nobs]      [nobs]      [nobs]      [nobs]      [nobs]      [nobs]      [nobs]
KP rk Wald F           [rkf]       [rkf]       [rkf]       [rkf]       [rkf]       [rkf]       [rkf]
Pre-COVID mean         [mean]      [mean]      [mean]      [mean]      [mean]      [mean]      [mean]

Role growth measure      -           ✓           ✓           ✓           ✓           ✓           ✓
```

Note: Scientist role may be column (8) if data is available

## Proposed Table 2: Seniority Composition Effects on Firm Scaling

```
                          (1)         (2)         (3)         (4)         (5)
                       Baseline   Level 1    Level 2    Level 3    Level 4
---------------------------------------------------------------------------
Panel A: OLS
Remote × Post          [var3]      [var3]      [var3]      [var3]      [var3]
                       (se)        (se)        (se)        (se)        (se)

Remote × Post × Startup [var5]      [var5]      [var5]      [var5]      [var5]
                       (se)        (se)        (se)        (se)        (se)

Panel B: IV
Remote × Post          [var3]      [var3]      [var3]      [var3]      [var3]
                       (se)        (se)        (se)        (se)        (se)

Remote × Post × Startup [var5]      [var5]      [var5]      [var5]      [var5]
                       (se)        (se)        (se)        (se)        (se)

N                      [nobs]      [nobs]      [nobs]      [nobs]      [nobs]
KP rk Wald F           [rkf]       [rkf]       [rkf]       [rkf]       [rkf]
Pre-COVID mean         [mean]      [mean]      [mean]      [mean]      [mean]

Seniority growth measure  -           ✓           ✓           ✓           ✓
```

## Key Design Decisions:

1. **Baseline Column**: 
   - Should we include a baseline without any composition controls?
   - Or use the first role/seniority as the baseline?

2. **Coefficient Selection**:
   - Show only var3 (Remote × Post) and var5 (Remote × Post × Startup)
   - Omit var4 (Post × Startup) to keep tables clean

3. **Statistics to Include**:
   - N (number of observations)
   - KP rk Wald F (first-stage F-stat for IV)
   - Pre-COVID mean of the growth measure

4. **Significance Stars**:
   - Calculate from t-statistics (coef/se)
   - *** p<0.01, ** p<0.05, * p<0.10

5. **Table Notes**:
   - Explain that these are firm-level scaling regressions
   - Clarify what the growth measures represent
   - Note fixed effects structure and clustering