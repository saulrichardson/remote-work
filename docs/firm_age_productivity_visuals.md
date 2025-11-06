# Firm Age vs. Productivity: Visualisation Paths

We want a figure that helps interpret the dynamic remote-work effects identified in `spec/stata/user_productivity.do`. Two complementary approaches are on the table:

---

## 1. Spec-Consistent (Frisch–Waugh–Lovell) Visual

**Purpose**  
Stay exactly aligned with the baseline regression so the figure is another view of the already-estimated `var5` effect.

**Key ingredients**

- Canonical model:  
  `reghdfe total_contributions_q100 var3 var5 var4, absorb(user_id firm_id yh)`  
  with `var5 = remote × covid × startup`.
- Controls to partial out alongside the fixed effects: `var3`, `var4`, `var6`, `var7`.
- Sample: `user_panel_precovid` (same filters as the spec).

**Implementation sketch**

1. Run the baseline regression in Stata (or replicate in Python).
2. Obtain residuals for the outcome and for `var5` after removing user, firm, and `yh` fixed effects plus the other regressors (FWL step).  
   *Python helper:* `src/py/plot_var5_effect_by_age.py` automates these steps and produces the firm-age figure.
3. To extend beyond the startup cutoff, interact `remote × covid` with broader age bins (or a continuous age term).  
   *Python helper:* `src/py/plot_remote_effect_by_age_bins.py` generalises the regression to remote×covid×age-bin interactions and plots the estimated remote effect across the full age range.
4. For a binscatter-style visual that keeps the same fixed effects/controls, run `spec/stata/scratch/binsreg_var5.do` to generate the binsreg residual figure or re-plot the saved data via `src/py/plot_binsreg_var5_from_savedata.py`.
3. Form the partial residual  
   `y_partial = y_resid + β̂₅ · var5`.
4. Collapse to the unit you want to plot (e.g. average `y_partial` by firm or by startup age bucket).
5. Plot `y_partial` (vertical axis) against firm age (horizontal axis). Because the residuals match the spec, the slope across age bins reflects the same `var5` coefficient shown in the tables.

**Pros / Cons**

- ✅ Fully consistent with published results.  
- ✅ Easy to reference in text (“Same spec as Table X; the figure just buckets by firm age”).  
- ⚠️ Requires working within the startup window (age ≤ 10) and makes sense only where `var5` is active (post-COVID remote exposure).

---

## 2. Exploratory Remote-Firm Scatter

**Purpose**  
Diagnostics / intuition-building. How do productivity residuals vary with continuous firm age for highly remote firms (e.g. GitHub) across pre/post periods?

**Outline**

1. Pull a subset of the panel (e.g. GitHub or other remote-heavy firms).  
2. Residualise productivity on individual and time fixed effects (optionally firm×individual).  
3. Plot the residuals vs. firm age, colouring points by pre/post pandemic.
4. Optionally add Loess trends or bin means.

**Pros / Cons**

- ✅ Highlights age trends across the full age range, not just the startup cut-off.  
- ✅ Intuitive and fast to interpret for a single firm or cohort.  
- ⚠️ Not the same model as the canonical spec; no `var3/var4/var6/var7` controls; ignores firm FE; should be labelled as exploratory.

---

## Recommended Sequence

1. **Spec-consistent visual** (Approach 1) for inclusion alongside the regression tables—this keeps the narrative anchored to existing identification.  
2. **Exploratory scatter** (Approach 2) as supplemental material if we need intuition for specific firms or broader age patterns; clearly mark it as a different model.

This note captures both paths so we can revisit or expand either one later.
