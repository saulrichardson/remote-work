# Heterogeneity of Remote-Work Productivity Effects  

This short note summarises four *within‐sample heterogeneity* checks that
split the user–half-year panel by firm or worker characteristics and re-runs
the baseline IV specification inside every bucket.  Each table is generated
automatically by `py/heterogeneity_table.py`; the underlying coefficients
correspond to `var3` (Remote × Post) and `var5` (Remote × Post × Startup).

| Table | Split variable (buckets) | File |
|-------|--------------------------|------|
| 1 | Modal vs. non-modal MSA (0 = outside, 1 = inside, 2 = missing) | [`var5_modal_base.tex`](var5_modal_base.tex) |
| 2 | Mean worker–firm distance (terciles) | [`var5_distance_base.tex`](var5_distance_base.tex) |
| 3 | *Dynamic* labour-growth **within** half-year (terciles) | [`var5_growth_base_dynamic.tex`](var5_growth_base_dynamic.tex) |
| 4 | Pre- vs. Post-COVID average labour-growth (terciles) | [`var5_growth_base_post.tex`](var5_growth_base_post.tex) |

Below we highlight the main take-aways; refer to the LaTeX tables for exact
standard errors and first-stage strength.

## 1. Modal-MSA split

* Remote workers seated **inside the modal MSA of the firm do **not** enjoy a
  positive productivity shock** – the point estimate is −14.7 but imprecise.
* Outside the modal location the triple interaction (var5) is **positive and
  significant** (+19.0), suggesting remote working benefits start-up
  employees who relocate away from HQ.

## 2. Distance terciles

* The negative Remote × Post effect attenuates strongly with distance: −22.3
  for the *nearest* tercile, −17.6 for the middle, essentially zero for the
  most distant workers.  The pattern is monotone and precisely estimated for
  the first two buckets.
* The triple interaction turns significantly positive only in the middle-
  distance group (+31.3).  This may capture start-ups that hire regionally
  rather than hyper-locally.

## 3. Dynamic labour-growth (within half-year)

* Firms experiencing **low contemporary growth** show a large negative remote
  effect (−21.7) whereas high-growth firms show none.  The middle bucket is
  noisy with an enormous point estimate and a vanishing first-stage F – treat
  with caution.

## 4. Labour-growth pre- vs. post-COVID

* The strongest negative remote effect is concentrated in firms that **grew
  the least** between the pre- and post-COVID periods (−16.4).  Firms with
  above-median growth see small and insignificant estimates.

---

### Overall

Across the cuts, negative productivity effects of remote status are most
pronounced

1. when workers stay geographically close to HQ (Tables 1–2), and
2. in firms with limited employment growth (Tables 3–4).

The triple interaction (Remote × Post × Startup) is positive in *some* bins
but is never large enough to offset the base remote effect in the same
bucket.  Selection into particular locations or firm types therefore shapes
the average treatment but does **not** reverse its sign.

All regressions rely on the same instrument set; KP-rk Wald F values stay
comfortably above the Stock–Yogo weak-IV cut-off (>10) except for the noisy
middle-growth bucket in Table 3.  Results for that group should be regarded
as exploratory.
