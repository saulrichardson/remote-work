// ----------------------------------------------------------------------
// Path bootstrap -------------------------------------------------------
// ----------------------------------------------------------------------
local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}
do "`__bootstrap'"



*============================================================*
* firm_remote_first_stage.do
* Summarises the cross-sectional link between firms' remote-work policies and
* their teleworkability index.  The script collapses to one observation per
* firm, runs the baseline first-stage regression, and exports the coefficient,
* partial F statistic, and fit diagnostics used in the first-stage summary.
*============================================================*

local specname   "firm_remote_first_stage"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text


// 0) Setup environment
do "../globals.do"
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
    double coef se pval partialF rkf nobs r2 ///
    using `out', replace

// 4) First-stage regression: Remote on Teleworkable
quietly regress remote teleworkable
    test teleworkable
    local coef  = _b[teleworkable]
    local se    = _se[teleworkable]
    local pval  = r(p)
    local fstat = r(F)
    local N     = e(N)
    local R2    = e(r2)

post handle ("remote") ("teleworkable") ///
    (`coef') (`se') (`pval') (`fstat') (.) (`N') (`R2')

// 5) Export results
postclose handle
use `out', clear
export delimited using "`result_dir'/first_stage.csv", ///
    replace delimiter(",") quote

display as result "→ first-stage CSV : `result_dir'/first_stage.csv'"

capture log close
