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

*======================================================================*
* plot_firm_age_productivity.do
* Stata recreation of the exploratory firm-age vs productivity plot
*======================================================================*

* --- Tunable parameters ---------------------------------------------*
local panel_variant  "precovid"    // which user panel to load
local outcome        "total_contributions_q100"
local remote_var     "remote"
local age_var        "age"
local user_fe        "user_id"
local time_fe        "yh"
local min_obs        10            // min worker obs per firm-period
local age_cap        100           // set missing to keep all ages
local age_bin_width  5             // set 0 to skip binning

local remote_breaks  "0 0.25 0.5 0.75 1.0001"
local remote_labels  `" "0–0.25" "0.25–0.50" "0.50–0.75" "0.75–1.00" "'

local out_dir        "$FINAL_FIGURES"
local out_name       "firm_age_vs_productivity_remote_bins"

* --- Load panel -----------------------------------------------------*
use "$processed_data/user_panel_`panel_variant'.dta", clear

keep `user_fe' `time_fe' firm_id `outcome' `remote_var' `age_var' covid
drop if missing(`user_fe', `time_fe', firm_id, `outcome', `remote_var', `age_var', covid)

* --- Residualise outcome on user & time FE --------------------------*
quietly summarize `outcome'
scalar __mean_outcome = r(mean)

reghdfe `outcome', absorb(`user_fe' `time_fe') resid
tempvar res
predict double `res', resid
generate double prod_adj = `res' + __mean_outcome

* --- Pre/Post indicator ---------------------------------------------*
generate byte period = (covid == 1)
label define period_lab 0 "Pre" 1 "Post"
label values period period_lab

* --- Optional age cap -----------------------------------------------*
if `age_cap' < . {
    keep if `age_var' <= `age_cap'
}

* --- Collapse to firm-period averages -------------------------------*
bysort firm_id period: egen n_obs = count(prod_adj)
keep if n_obs >= `min_obs'

collapse (mean) prod_adj `remote_var' `age_var' ///
         (sum)  n_obs, by(firm_id period)

* Marker size (scaled by sqrt of worker count)
generate double msize = sqrt(n_obs)
quietly summarize msize
replace msize = 0.8 * msize / r(max)
replace msize = max(msize, 0.2)

* --- Optional age binning -------------------------------------------*
if `age_bin_width' > 0 {
    quietly summarize `age_var'
    local max_age = ceil(r(max) / `age_bin_width') * `age_bin_width'

    egen age_bin = cut(`age_var'), at(0(`age_bin_width')`max_age') icodes
    egen age_mid = mean(`age_var'), by(age_bin period)
    egen prod_bin = mean(prod_adj), by(age_bin period)
    egen remote_bin = mean(`remote_var'), by(age_bin period)
    egen n_obs_bin = total(n_obs), by(age_bin period)

    drop if missing(age_bin)
    bysort age_bin period: keep if _n == 1

    replace `age_var'    = age_mid
    replace prod_adj     = prod_bin
    replace `remote_var' = remote_bin
    replace n_obs        = n_obs_bin

    replace msize = sqrt(n_obs)
    quietly summarize msize
    replace msize = 0.8 * msize / r(max)
    replace msize = max(msize, 0.2)
}

* --- Remote-share buckets (discrete colouring) ----------------------*
egen remote_cat = cut(`remote_var'), at(`remote_breaks') icodes
label define remote_lab 1 "0–0.25" 2 "0.25–0.50" 3 "0.50–0.75" 4 "0.75–1.00"
label values remote_cat remote_lab

levelsof remote_cat, local(remote_levels)
local remote_colors "gs12 skyblue midblue navy"

* --- Build the scatter ----------------------------------------------*
local plot ""
local idx = 1
local i = 1
foreach lvl of local remote_levels {
    local color : word `i' of `remote_colors'
    local lbl : label remote_lab `lvl'

    local plot `plot' ///
        (scatter prod_adj `age_var' if period==0 & remote_cat==`lvl', ///
            msymbol(circle) mcolor(`color') msize(msize) ///
            legend(label(`idx' "Pre, remote `lbl'")))
    local idx = `idx' + 1

    local plot `plot' ///
        (scatter prod_adj `age_var' if period==1 & remote_cat==`lvl', ///
            msymbol(square) mcolor(`color') msize(msize) ///
            legend(label(`idx' "Post, remote `lbl'")))

    local i = `i' + 1
    local idx = `idx' + 1
}

local pre_trend = `idx'
local post_trend = `idx' + 1

local plot `plot' ///
    (lfit prod_adj `age_var' if period==0, lcolor(gs8) lpattern(dash) ///
        legend(label(`pre_trend' "Pre trend"))) ///
    (lfit prod_adj `age_var' if period==1, lcolor(gs4) lpattern(dash_dot) ///
        legend(label(`post_trend' "Post trend")))

twoway `plot', ///
    xtitle("Firm age (years)") ///
    ytitle("Productivity residual (user/time FE + mean)") ///
    title("Firm age vs. productivity residuals") ///
    note("Circles = Pre, Squares = Post. Marker size ∝ worker observations.") ///
    legend(order(1/`post_trend') col(1) position(6) ring(0) size(small)) ///
    graphregion(color(white)) ///
    bgcolor(white)

graph export "`out_dir'/`out_name'.png", replace width(2000)

di as result "→ Saved plot to `out_dir'/`out_name'.png"
