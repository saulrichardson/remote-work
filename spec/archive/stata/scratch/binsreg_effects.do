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
* binsreg_effects.do
* Generate binsreg curves for var3, var4, and var5 in a spec-consistent way
*======================================================================*

capture which binsreg
if _rc {
    di as error "binsreg not found. Install via: ssc install binsreg"
    exit 199
}

local project_root "/Users/saul/Dropbox/Remote Work Startups/main"
local input        "`project_root'/data/processed/user_panel_precovid.dta"
local outdir       "`project_root'/results/cleaned/figures"

local effects "var3 var4 var5"

foreach eff of local effects {
    use "`input'", clear

    if "`eff'" == "var5" {
        keep if startup == 1
    }

    if "`eff'" == "var4" {
        keep if age <= 10
    }

    keep user_id firm_id yh age total_contributions_q100 var3 var4 var5
    drop if missing(user_id, firm_id, yh, age, total_contributions_q100, var3, var4, var5)

    tempvar treat
    gen byte `treat' = (`eff' > 0)

    if "`eff'" == "var3" {
        label define treat_lab 0 "Baseline" 1 "Remote × COVID"
    }
    else if "`eff'" == "var4" {
        label define treat_lab 0 "Non-startup / pre" 1 "Startup × COVID"
    }
    else if "`eff'" == "var5" {
        label define treat_lab 0 "Startup baseline" 1 "Startup remote × COVID"
    }
    label values `treat' treat_lab

    * controls exclude the effect of interest
    local controls "var3 var4 var5"
    local controls : list controls - eff

    reghdfe total_contributions_q100 `controls', absorb(user_id firm_id yh) vce(cluster firm_id) resid
    predict double contrib_resid, resid

    local fig "`outdir'/binsreg_`eff'_levels.png"
    local lineopt "line(1 0)"
    if "`eff'" == "var4" local lineopt "line(0 0)"

    binsreg contrib_resid age, by(`treat') samebinsby nbins(10) binspos(es) masspoints(off) ///
        dots(1 0) ci(1 0) `lineopt' ///
        title("`eff' effect vs. firm age") ///
        xtitle("Firm age (years)") ytitle("Contribution residual")

    graph export "`fig'", width(2400) replace
    di as result "→ Saved `fig'"
}
