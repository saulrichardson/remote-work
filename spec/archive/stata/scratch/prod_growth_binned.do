*--------------------------------------------------------------------
* prod_growth_binned.do
* Cross-section diagnostic: change in typical worker rank vs firm growth.
* Data prep is done in Python (src/py/prod_growth_deltas.py).
* This script:
*   - runs the firm-level regression
*   - creates a binned scatter (manual bins) and two histograms
* Outputs saved under results/diagnostics/.
*--------------------------------------------------------------------

local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}
do "`__bootstrap'"

capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/prod_growth_binned.log", replace text

local diag_dir "$PROJECT_ROOT/results/diagnostics"
cap mkdir "`diag_dir'"

use "`diag_dir'/prod_growth_diff_balanced.dta", clear

* Restrict to fully remote firms only
keep if remote_flag == 1

keep if !missing(d_rank_med, diff_growth)

*-----------------------------
* Regressions (stayer delta and composition-inclusive level change)
*-----------------------------

tempfile reg_out
capture postclose handle
postfile handle str15 model str20 param double coef se pval nobs r2 using `reg_out', replace

* Model 1: stayer-based median delta
reg d_rank_med diff_growth startup [aw=n_users], vce(robust)
local __N = e(N)
local __r2 = e(r2)
foreach p in diff_growth startup {
    local b = _b[`p']
    local se = _se[`p']
    local t = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle ("stayer") ("`p'") (`b') (`se') (`pval') (`__N') (`__r2')
}

* Model 2: firm-level mean rank change (composition-inclusive)
reg diff_rank_level diff_growth startup [aw=n_users_all], vce(robust)
local __N2 = e(N)
local __r2_2 = e(r2)
foreach p in diff_growth startup {
    local b = _b[`p']
    local se = _se[`p']
    local t = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle ("level") ("`p'") (`b') (`se') (`pval') (`__N2') (`__r2_2')
}

postclose handle
use `reg_out', clear
export delimited using "`diag_dir'/prod_growth_regression.csv", replace

*-----------------------------
* Binned scatter (stayer metric) using binsreg
*-----------------------------
use "`diag_dir'/prod_growth_diff_balanced.dta", clear
keep if remote_flag == 1
keep if !missing(d_rank_med, diff_growth)

binsreg d_rank_med diff_growth [aw=n_users], nbins(20) polyreg(1) ci(0) ///
    dotsplotopt(msize(medium) mcolor(navy)) ///
    polyregplotopt(lcolor(gs6) lwidth(medthick)) ///
    xtitle("Post – Pre growth rate (winsorised)") ///
    ytitle("Median within-user rank change") ///
    title("Change in productivity vs firm growth (stayers)")
graph export "`diag_dir'/binscatter_prod_growth_stayer.png", replace width(1600) height(1200)

*-----------------------------
* Binned scatter (composition-inclusive mean rank change) using binsreg
*-----------------------------
use "`diag_dir'/prod_growth_diff_balanced.dta", clear
keep if remote_flag == 1
keep if !missing(diff_rank_level, diff_growth)

binsreg diff_rank_level diff_growth [aw=n_users_all], nbins(20) polyreg(1) ci(0) ///
    dotsplotopt(msize(medium) mcolor(teal)) ///
    polyregplotopt(lcolor(gs6) lwidth(medthick)) ///
    xtitle("Post – Pre growth rate (winsorised)") ///
    ytitle("Mean rank change (all workers)") ///
    title("Change in productivity vs firm growth (all workers)")
graph export "`diag_dir'/binscatter_prod_growth_level.png", replace width(1600) height(1200)

*-----------------------------
* Histograms: remote firms only, startup vs incumbent (stayer metric)
*-----------------------------
use "`diag_dir'/prod_growth_diff_balanced.dta", clear
keep if remote_flag == 1

twoway (hist d_rank_med if startup, color(navy%55) width(2)) ///
       (hist d_rank_med if !startup, color(maroon%55) width(2)), ///
       legend(order(1 "Remote startups" 2 "Remote incumbents")) ///
       xtitle("Median within-user rank change") ///
       title("Productivity change distribution (stayers)")
graph export "`diag_dir'/hist_prod_change_stayer.png", replace width(1600) height(1200)

twoway (hist diff_growth if startup, color(navy%55) width(.02)) ///
       (hist diff_growth if !startup, color(maroon%55) width(.02)), ///
       legend(order(1 "Remote startups" 2 "Remote incumbents")) ///
       xtitle("Growth rate change") ///
       title("Growth change distribution")
graph export "`diag_dir'/hist_growth_change.png", replace width(1600) height(1200)

*-----------------------------
* Histograms: remote firms, composition-inclusive rank change
*-----------------------------
twoway (hist diff_rank_level if startup, color(teal%55) width(2)) ///
       (hist diff_rank_level if !startup, color(orange%55) width(2)), ///
       legend(order(1 "Remote startups" 2 "Remote incumbents")) ///
       xtitle("Mean rank change (all workers)") ///
       title("Productivity change distribution (all workers)")
graph export "`diag_dir'/hist_prod_change_level.png", replace width(1600) height(1200)

di as result "Outputs written to `diag_dir'"
log close
