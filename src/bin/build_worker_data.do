*------------------------------------------------------------*
* src/build_worker_data.do
* Build and clean worker-level data into master_worker.dta.
*------------------------------------------------------------*

* 0) load globals and ensure firm data is ready
do "src/globals2.do"
do "src/build_firm_data.do"

* 1) Add worker ↔ HQ MSA distances
do "../do/distances.do"

* 2) Merge employee counts by firm & half-year
do "../exploratory_analysis/merging employyes.do"

* 3) Compute worker productivity residuals
do "../exploratory_analysis/productivity_residual.do"

* 4) [Optional] Additional worker-level merges (e.g., telework, contributions)

* 5) Save worker-level master panel
capture mkdir "$data"
save "$data/master_worker.dta", replace

di as result "✅ Worker-level data build complete: $data/master_worker.dta"