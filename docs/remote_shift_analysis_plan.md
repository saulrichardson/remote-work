# Plan: Testing Shift to Remote Work vs Geographic Expansion

## Research Question
Are remote-enabled firms shifting workers from legacy office locations to **remote work** rather than to new physical locations?

## Current Analysis Gap
- Current metric: Share of MSA-defined hires in new locations (~15% reduction for remote firms)
- Missing: Workers hired as remote (msa='empty') who would have been in offices pre-pandemic
- These remote workers are currently excluded from our geographic expansion metric

## Proposed Analysis Framework

### 1. Three-Way Classification of Post-2019 Hires
Instead of binary (legacy vs new MSA), classify all hires as:
- **Legacy MSA**: Hired in traditional office locations
- **New MSA**: Hired in new physical locations  
- **Remote**: Hired without MSA designation (msa='empty')

### 2. Key Metrics to Calculate

#### A. Comprehensive Hiring Shares (must sum to 100%)
- `share_legacy_msa` = legacy MSA hires / total hires
- `share_new_msa` = new MSA hires / total hires
- `share_remote` = remote hires / total hires

#### B. Substitution Metrics
- `remote_substitution_rate` = remote hires / (remote + new MSA hires)
  - If close to 1: remote substitutes for geographic expansion
  - If close to 0: firms expand geographically without remote

#### C. Total Geographic Dispersion
- `total_dispersion` = (new MSA hires + remote hires) / total hires
  - Captures both physical and virtual geographic expansion

## Data Requirements

### Need to Access
1. **Raw LinkedIn data WITH empty MSAs**
   - Currently filtered out in linkedin_panel.parquet
   - Need to create new panel that includes msa='empty' rows

2. **Firm×Period Aggregation Including Remote**
   - Total hires (all types)
   - Remote hires (msa='empty')  
   - MSA hires (non-empty)
   - Legacy MSA hires
   - New MSA hires

## Implementation Steps

### Phase 1: Data Preparation
1. Create `linkedin_panel_with_remote.parquet`
   - Include ALL rows from raw data
   - Add flag: `is_remote = (msa == 'empty')`
   - Keep firm, yh, soc, msa, headcount, joins, leaves

2. Update legacy location identification
   - No change needed (2019-H2 baseline remains the same)
   - Remote workers in 2019 don't define legacy locations

### Phase 2: Calculate New Metrics
1. Build comprehensive hiring classification
   ```python
   # For each firm×period:
   remote_hires = hires where msa='empty'
   legacy_msa_hires = hires where msa in legacy_locations
   new_msa_hires = hires where msa not in legacy_locations and msa != 'empty'
   total_hires = remote_hires + legacy_msa_hires + new_msa_hires
   ```

2. Calculate shares and substitution metrics

### Phase 3: Regression Analysis
Run three parallel regressions:

```stata
// 1. Original: Physical geographic expansion only
ivreghdfe share_new_msa (var3 var5 = var6 var7) var4, absorb(firm_id yh)

// 2. Remote hiring share
ivreghdfe share_remote (var3 var5 = var6 var7) var4, absorb(firm_id yh)

// 3. Total dispersion (new MSA + remote)
ivreghdfe total_dispersion (var3 var5 = var6 var7) var4, absorb(firm_id yh)
```

### Phase 4: Substitution Analysis
Test whether remote substitutes for or complements physical expansion:

```stata
// Create interaction
gen new_msa_x_remote = share_new_msa * share_remote

// Test correlation
reg share_new_msa share_remote if covid==1, cluster(firm_id)
// Negative coefficient → substitution
// Positive coefficient → complement
```

## Expected Outcomes

### Scenario A: Pure Substitution
- `share_new_msa` ↓ for remote firms (current finding: -15pp)
- `share_remote` ↑ for remote firms (by similar magnitude)
- `total_dispersion` ≈ unchanged
- **Interpretation**: Remote work substitutes for physical expansion

### Scenario B: Additional Dispersion  
- `share_new_msa` ↓ for remote firms
- `share_remote` ↑↑ for remote firms (more than MSA decline)
- `total_dispersion` ↑ for remote firms
- **Interpretation**: Remote enables greater total geographic dispersion

### Scenario C: Concentration
- `share_new_msa` ↓ for remote firms
- `share_remote` ↑ slightly
- `share_legacy_msa` ↑ (most growth in traditional locations)
- **Interpretation**: Remote firms concentrate in existing hubs

## Validation Checks

1. **Known Remote-First Companies**
   - GitLab, Zapier, etc. should show high `share_remote`
   - Validate our remote classification

2. **Industry Patterns**
   - Tech firms should show higher remote adoption
   - Manufacturing should show lower remote adoption

3. **Time Trends**
   - Remote share should increase post-2020
   - Especially for treated (remote-enabled) firms

## Key Advantages of This Approach

1. **Complete Picture**: Captures all hiring, not just MSA-defined
2. **Identifies Substitution**: Tests if remote replaces geographic expansion
3. **Policy Relevant**: Distinguishes virtual vs physical dispersion
4. **Validates Current Finding**: If remote substitutes for new MSAs, the -15% effect makes sense

## Potential Challenges

1. **Data Size**: Including empty MSAs adds ~45% more data
2. **Classification**: Some "empty" might be data quality issues, not true remote
3. **Pre-Period**: Can't measure "new remote" in pre-period (no baseline)

## Next Steps

1. **Validate feasibility**: Check if raw data still accessible
2. **Test on sample**: Run on 1% sample to verify approach
3. **Full implementation**: If validated, run complete analysis
4. **Robustness**: Test sensitivity to remote classification

This approach would definitively answer whether remote work substitutes for or complements geographic expansion.