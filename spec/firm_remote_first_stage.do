*============================================================*
*  do/firm_remote_first_stage.do
*  — Basic first-stage regression of Remote on Teleworkable
*============================================================*

capture log close
local specname   "firm_remote_first_stage"
log using "log/`specname'.log", replace text

// 0) Setup environment
do "../src/globals.do"
local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

// 1) Load firm-level panel
use "$processed_data/firm_panel.dta", clear

// 2) Keep one observation per firm
bysort firm_id: keep if _n == 1

// 3) Prepare postfile for results
capture postclose handle
tempfile out
postfile handle ///
    str20 endovar ///
    str20 param   ///
    double coef se pval partialF rkf nobs ///
    using `out', replace

// 4) First-stage regression: Remote on Teleworkable
quietly regress remote teleworkable
    test teleworkable
    local coef  = _b[teleworkable]
    local se    = _se[teleworkable]
    local pval  = r(p)
    local fstat = r(F)
    local N     = e(N)

post handle ("remote") ("teleworkable") ///
    (`coef') (`se') (`pval') (`fstat') (.) (`N')

// 5) Export results
postclose handle
use `out', clear
export delimited using "`result_dir'/first_stage.csv", ///
    replace delimiter(",") quote

display as result "→ first-stage CSV : `result_dir'/first_stage.csv'"

capture log close
