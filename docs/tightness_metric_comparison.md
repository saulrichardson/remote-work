# Labour-Supply Tightness — definitions, differences and trade-offs

This note compares the **tightness index currently produced by the Python
pipeline** with the **“HQ–scalar share-based” index** proposed in the
scaling-meeting deck.  Differences arise on two axes:

| Axis | Pipeline (current) | Meeting proposal |
|------|--------------------|------------------|
| *Supply statistic*  𝘴<sub>mo</sub> | **Inverse location quotient** (share<sub>US</sub>/share<sub>metro</sub>) | **Simple share** (national *or* local) |
| *Metro aggregation* | **Head-count-weighted average over all CBSAs** where the firm had workers in 2019 | **Single HQ CBSA only** |

---

## 1  Supply statistics

For every metro *m* and occupation *o* we can form three candidate measures:

| Statistic | Formula | Interpretation |
|-----------|---------|----------------|
| National share | 𝘴<sup>nat</sup><sub>mo</sub> = Emp<sub>mo</sub>/∑<sub>m′</sub>Emp<sub>m′o</sub> | “What fraction of all U.S. *o*-jobs are in this metro?” |
| Local share | 𝘴<sup>loc</sup><sub>mo</sub> = Emp<sub>mo</sub>/Jobs<sub>m</sub> | “How concentrated is *o* in this metro’s workforce?” |
| **Inverse LQ** *(pipeline)* | 𝘴<sup>LQ-¹</sup><sub>mo</sub> = ( Emp<sub>o</sub><sup>US</sup>/Jobs<sup>US</sup> ) ÷ ( Emp<sub>mo</sub>/Jobs<sub>m</sub> ) | “Scarcity of *o* locally relative to nation” (< 1 = abundant, > 1 = scarce) |

The current code uses the **inverse location quotient**.

---

## 2  Two-stage aggregation (common skeleton)

1. **Within an occupation, across CBSAs**

   Tight<sub>io</sub> = ∑<sub>m</sub> *w*<sub>imo</sub><sup>2019</sup> · 𝘴<sub>mo</sub>

   where *w*<sub>imo</sub> are the firm’s 2019 head-count shares of occupation *o*
   across metros.  In the HQ-scalar case these weights collapse to 1 on
   HQ and 0 elsewhere.

2. **Across occupations to the firm scalar**

   Tight<sub>i</sub> = ∑<sub>o</sub> *w*<sub>io</sub><sup>2019</sup> · Tight<sub>io</sub>,
   with *w*<sub>io</sub> the 2019 occupation mix of the firm.

Only the choice of 𝘴<sub>mo</sub> and the *w*<sub>imo</sub> weights differs between
variants; the weighting machinery is identical.

---

## 3  Pros & cons

### A  Supply statistic

| Choice | Pros | Cons |
|--------|------|------|
| **Inverse LQ** (current) | • Captures scarcity vs. national baseline.<br>• Unit-free across occupations. | • Harder intuition; needs national totals. |
| National share | • Simplest; only metro occupation counts needed. | • Favors very large occupations; metro size ignored. |
| Local share | • Purely local normalisation. | • Not comparable across differently-sized metros. |

### B  Metro aggregation strategy

| Choice | Pros | Cons |
|--------|------|------|
| **All metros** (current) | • Reflects where the firm actually hired in 2019.<br>• Robust to HQ miscoding. | • Dilutes “home-market” narrative;<br>  needs full metro breakdown. |
| **HQ metro only** | • Matches story “constraint in home market”.<br>• Simplest to explain & implement. | • Ignores other large sites.<br>• Sensitive to HQ definition; OEWS gaps hurt coverage. |

---

## 4  Relationship between the two metrics

* If a firm operated in only one CBSA in 2019 (or if we force
  *w*<sub>imo</sub>=1 for HQ), **both formulas coincide**.
* Otherwise they deviate because the pipeline averages over multiple
  metros whereas the proposal keeps only HQ.

Both remain two-stage weighted sums; you can switch from one to the other by

1. swapping the OEWS column used for 𝘴<sub>mo</sub> (share vs. inverse-LQ), and/or
2. replacing the CBSA weights *w*<sub>imo</sub> with a (1,0,0,…) vector for HQ.

---

## 5  Practical recommendation

*Keep both.*  Generate the HQ-scalar in addition to the existing
multi-metro inverse-LQ index and include each in separate or joint
regressions:

```stata
ivreghdfe growth_rate_we  ///
    (remote#post#tight_hq   =  remote#post#teleworkable) ///
    controls, absorb(firm_id#yh) vce(cluster firm_id)

ivreghdfe growth_rate_we  ///
    (remote#post#tight_multi = remote#post#teleworkable) ///
    controls, absorb(firm_id#yh) vce(cluster firm_id)
```

Consistent signs strengthen the story; divergences tell you which
dimension of “tightness” drives the remote-work gains.
