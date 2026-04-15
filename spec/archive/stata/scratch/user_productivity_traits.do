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
*  spec/user_productivity_traits.do
*  Variant of user productivity IV spec with worker traits.
*  - Merges in user_attributes.dta on the fly (no changes to panels)
*  - Runs baseline OLS/IV plus heterogeneity via interaction IV
*    and split-sample IV for selected worker characteristics.
*============================================================*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

local specname  "user_productivity_traits_`panel_variant'"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text


* ------------------------------------------------------------
* 0) Environment & data
* ------------------------------------------------------------
local project_root : env STATAROOT
if "`project_root'" != "" {
    local globals_path "`project_root'/src/globals.do"
} 
else {
    local globals_path "../globals.do"
}

do "`globals_path'"

if "`project_root'" != "" {
    global raw_data        "`project_root'/data/raw"
    global processed_data  "`project_root'/data/processed"
    global results         "`project_root'/results/raw"
    global clean_results   "`project_root'/results/cleaned"
}

local result_dir "$results/`specname'"
cap mkdir "`result_dir'"

use "$processed_data/user_panel_`panel_variant'.dta", clear

merge m:1 user_id using "$processed_data/user_attributes.dta", ///
    keep(match master) nogen

* ------------------------------------------------------------
* 1) Trait construction
* ------------------------------------------------------------

* Gender flag (missing when probabilities unavailable)
gen byte female_flag = .
replace female_flag = 1 if gender_category == "female"
replace female_flag = 0 if inlist(gender_category, "male", "undetermined")

* Graduate degree (masters+) and doctorate indicators
gen byte graddeg_flag = .
replace graddeg_flag = 1 if has_graduate_degree == 1
replace graddeg_flag = 0 if has_graduate_degree == 0

gen byte doctorate_flag = .
replace doctorate_flag = 1 if has_doctorate == 1
replace doctorate_flag = 0 if has_doctorate == 0

* Approx age cleaning and buckets
gen double approx_age = approx_age_2020
replace approx_age = . if approx_age < 18 | approx_age > 80

gen byte age_under30 = .
replace age_under30 = 1 if approx_age < 30
replace age_under30 = 0 if approx_age >= 30 & !missing(approx_age)

gen byte age_40plus = .
replace age_40plus = 1 if approx_age >= 40
replace age_40plus = 0 if approx_age < 40 & approx_age >= 18 & !missing(approx_age)

gen byte age_25_45_flag = .
replace age_25_45_flag = 1 if approx_age >= 25 & approx_age <= 45
replace age_25_45_flag = 0 if approx_age < 25 & approx_age >= 18 & !missing(approx_age)
replace age_25_45_flag = 0 if approx_age > 45 & approx_age <= 80 & !missing(approx_age)

* Elite school lookup (case-insensitive on USA name)
#delimit ;
local elite_list `" "harvard university"
    "stanford university"
    "massachusetts institute of technology"
    "university of california, berkeley"
    "university of chicago"
    "university of pennsylvania"
    "princeton university"
    "yale university"
    "columbia university"
    "cornell university"
    "brown university"
    "dartmouth college"
    "duke university"
    "northwestern university"
    "university of michigan"
    "university of california, los angeles"
    "california institute of technology"
    "carnegie mellon university"
    "new york university"
    "university of texas at austin" "';
#delimit cr

gen strL school_clean = lower(highest_university_name_usa)
gen byte top_school_flag = .
replace top_school_flag = 0 if !missing(school_clean)
foreach school in `elite_list' {
    replace top_school_flag = 1 if strpos(school_clean, "`school'") > 0
}
replace top_school_flag = . if missing(school_clean)
replace top_school_flag = . if trim(school_clean) == ""

drop school_clean

* ------------------------------------------------------------
* 2) Result containers
* ------------------------------------------------------------

capture postclose handle
tempfile out
postfile handle ///
    str8   model_type ///
    str40  outcome ///
    str20  trait ///
    str40  param ///
    double coef se pval pre_mean rkf nobs ///
    using `out', replace

capture postclose handle_split
tempfile out_split
postfile handle_split ///
    str8   model_type ///
    str40  outcome ///
    str20  trait ///
    str8   group ///
    str40  param ///
    double coef se pval pre_mean rkf nobs ///
    using `out_split', replace

local outcomes total_contributions_q100
local traits female_flag graddeg_flag doctorate_flag top_school_flag age_under30 age_40plus age_25_45_flag

* ------------------------------------------------------------
* 3) Baseline (no interactions)
* ------------------------------------------------------------
foreach y of local outcomes {
    summarize `y' if covid == 0, meanonly
    local pre_mean = r(mean)

    reghdfe `y' var3 var5 var4, absorb(user_id#firm_id yh) vce(cluster user_id)
    local N = e(N)
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("OLS") ("`y'") ("baseline") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') (.) (`N')
    }

    ivreghdfe `y' (var3 var5 = var6 var7) var4, ///
        absorb(user_id#firm_id yh) vce(cluster user_id)
    local rkf = e(rkf)
    local N   = e(N)
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("IV") ("`y'") ("baseline") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') (`rkf') (`N')
    }

}

* ------------------------------------------------------------
* 4) Trait interactions (quadruple-IV)
* ------------------------------------------------------------

foreach trait of local traits {
    count if !missing(`trait')
    if r(N) == 0 continue

    local suffix "_`trait'"
    foreach y of local outcomes {
        summarize `y' if covid == 0 & !missing(`trait'), meanonly
        if r(N) == 0 continue
        local pre_mean = r(mean)

        capture drop var3`suffix' var5`suffix' var4`suffix' var6`suffix' var7`suffix'
        gen double var3`suffix' = var3 * `trait'
        gen double var5`suffix' = var5 * `trait'
        gen double var4`suffix' = var4 * `trait'
        gen double var6`suffix' = var6 * `trait'
        gen double var7`suffix' = var7 * `trait'

        reghdfe `y' var3 var5 var4 ///
            var3`suffix' var5`suffix' var4`suffix' ///
            if !missing(`trait'), absorb(user_id#firm_id yh) ///
            vce(cluster user_id)
        local N = e(N)
        foreach p in var3 var5 var4 var3`suffix' var5`suffix' var4`suffix' {
            local b    = _b[`p']
            local se   = _se[`p']
            local t    = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            post handle ("OLS") ("`y'") ("`trait'") ("`p'") ///
                (`b') (`se') (`pval') (`pre_mean') (.) (`N')
        }

        ivreghdfe `y' (var3 var5 var3`suffix' var5`suffix' = ///
            var6 var7 var6`suffix' var7`suffix') ///
            var4 var4`suffix' ///
            if !missing(`trait'), absorb(user_id#firm_id yh) ///
            vce(cluster user_id)
        local rkf = e(rkf)
        local N   = e(N)
        foreach p in var3 var5 var4 var3`suffix' var5`suffix' var4`suffix' {
            local b    = _b[`p']
            local se   = _se[`p']
            local t    = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            post handle ("IV") ("`y'") ("`trait'") ("`p'") ///
                (`b') (`se') (`pval') (`pre_mean') (`rkf') (`N')
        }

        drop var3`suffix' var5`suffix' var4`suffix' var6`suffix' var7`suffix'
    }
}

* ------------------------------------------------------------
* 5) Split-sample IV
* ------------------------------------------------------------
foreach trait of local traits {
    foreach group in 1 0 {
        count if `trait' == `group'
        if r(N) == 0 continue
        foreach y of local outcomes {
            summarize `y' if covid == 0 & `trait' == `group', meanonly
            if r(N) == 0 continue
            local pre_mean = r(mean)

            reghdfe `y' var3 var5 var4 ///
                if `trait' == `group', absorb(user_id#firm_id yh) ///
                vce(cluster user_id)
            local N = e(N)
            foreach p in var3 var5 var4 {
                local b    = _b[`p']
                local se   = _se[`p']
                local t    = `b'/`se'
                local pval = 2*ttail(e(df_r), abs(`t'))
                post handle_split ("OLS") ("`y'") ("`trait'") ("`group'") ("`p'") ///
                    (`b') (`se') (`pval') (`pre_mean') (.) (`N')
            }

            ivreghdfe `y' (var3 var5 = var6 var7) var4 ///
                if `trait' == `group', absorb(user_id#firm_id yh) ///
                vce(cluster user_id)
            local rkf = e(rkf)
            local N   = e(N)
            foreach p in var3 var5 var4 {
                local b    = _b[`p']
                local se   = _se[`p']
                local t    = `b'/`se'
                local pval = 2*ttail(e(df_r), abs(`t'))
                post handle_split ("IV") ("`y'") ("`trait'") ("`group'") ("`p'") ///
                    (`b') (`se') (`pval') (`pre_mean') (`rkf') (`N')
            }
        }
    }
}

* ------------------------------------------------------------
* 6) Export results
* ------------------------------------------------------------
postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", ///
    replace delimiter(",") quote

postclose handle_split
use `out_split', clear
export delimited using "`result_dir'/split_results.csv", ///
    replace delimiter(",") quote

di as result "→ Output directory: `result_dir'"
log close
