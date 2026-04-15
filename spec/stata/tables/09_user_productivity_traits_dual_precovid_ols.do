*============================================================*
* Asset 09: user_productivity_traits_dual_precovid_ols.tex
* Focused heterogeneity spec for Female + Age 25–45 traits.
* Runs baseline OLS/IV and trait interactions for two FE sets:
*   (i) user × firm pair + time FE
*  (ii) user FE + firm FE + time FE
*============================================================*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

local specname  "09_user_productivity_traits_dual_`panel_variant'_ols"

// ------------------------------------------------------------
// 0) Environment & data
// ------------------------------------------------------------
local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}
do "`__bootstrap'"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text



use "$processed_data/user_panel_`panel_variant'.dta", clear
merge m:1 user_id using "$processed_data/user_attributes.dta", ///
    keep(match master) nogen


// ------------------------------------------------------------
// 1) Trait construction (Female + Age 25–45)
// ------------------------------------------------------------
gen byte female_flag = .
replace female_flag = 1 if gender_category == "female"
replace female_flag = 0 if inlist(gender_category, "male", "undetermined")

gen double approx_age = approx_age_2020
replace approx_age = . if approx_age < 18 | approx_age > 80

gen byte age_25_45_flag = .
replace age_25_45_flag = 1 if approx_age >= 25 & approx_age <= 45
replace age_25_45_flag = 0 if approx_age < 25 & approx_age >= 18 & !missing(approx_age)
replace age_25_45_flag = 0 if approx_age > 45 & approx_age <= 80 & !missing(approx_age)

drop approx_age

tempfile trait_panel
save `trait_panel', replace

// ------------------------------------------------------------
// 2) Result containers
// ------------------------------------------------------------
local result_dir "$results/`specname'"
cap mkdir "`result_dir'"

capture postclose handle
tempfile out
postfile handle ///
    str8   model_type ///
    str20  fe_tag ///
    str40  outcome ///
    str20  trait ///
    str40  param ///
    double coef se pval pre_mean rkf nobs ///
    using `out', replace

// ------------------------------------------------------------
// 3) Estimation loops
// ------------------------------------------------------------
local outcomes total_contributions_q100 total_contributions_we
local traits   female_flag age_25_45_flag
local fe_tags  "firmbyuseryh fyhu"

foreach fe_tag of local fe_tags {
    use `trait_panel', clear
    if "`fe_tag'" == "firmbyuseryh" {
        local feopt "absorb(user_id#firm_id yh)"
    }
    else if "`fe_tag'" == "fyhu" {
        local feopt "absorb(user_id firm_id yh)"
    }
    else {
        di as error "Unknown fe_tag `fe_tag'"
        continue
    }

    foreach y of local outcomes {
        summarize `y' if covid == 0, meanonly
        local pre_mean = r(mean)

        // ----- OLS -----
        reghdfe `y' var3 var5 var4, `feopt' vce(cluster user_id)
        local N = e(N)
        foreach p in var3 var5 var4 {
            local b    = _b[`p']
            local se   = _se[`p']
            local t    = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            post handle ///
                ("OLS") ("`fe_tag'") ("`y'") ("baseline") ("`p'") ///
                (`b') (`se') (`pval') (`pre_mean') (.) (`N')
        }

        // ----- IV -----
        ivreghdfe `y' (var3 var5 = var6 var7) var4, ///
            `feopt' vce(cluster user_id)
        local rkf = e(rkf)
        local N   = e(N)
        foreach p in var3 var5 var4 {
            local b    = _b[`p']
            local se   = _se[`p']
            local t    = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            post handle ///
                ("IV") ("`fe_tag'") ("`y'") ("baseline") ("`p'") ///
                (`b') (`se') (`pval') (`pre_mean') (`rkf') (`N')
        }

    }

    // ----- Trait interactions (quadruple IV) -----
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
                if !missing(`trait'), `feopt' ///
                vce(cluster user_id)
            local N = e(N)
            foreach p in var3 var5 var4 var3`suffix' var5`suffix' var4`suffix' {
                local b    = _b[`p']
                local se   = _se[`p']
                local t    = `b'/`se'
                local pval = 2*ttail(e(df_r), abs(`t'))
                post handle ///
                    ("OLS") ("`fe_tag'") ("`y'") ("`trait'") ("`p'") ///
                    (`b') (`se') (`pval') (`pre_mean') (.) (`N')
            }

            ivreghdfe `y' (var3 var5 var3`suffix' var5`suffix' = ///
                var6 var7 var6`suffix' var7`suffix') ///
                var4 var4`suffix' ///
                if !missing(`trait'), `feopt' ///
                vce(cluster user_id)
            local rkf = e(rkf)
            local N   = e(N)
            foreach p in var3 var5 var4 var3`suffix' var5`suffix' var4`suffix' {
                local b    = _b[`p']
                local se   = _se[`p']
                local t    = `b'/`se'
                local pval = 2*ttail(e(df_r), abs(`t'))
                post handle ///
                    ("IV") ("`fe_tag'") ("`y'") ("`trait'") ("`p'") ///
                    (`b') (`se') (`pval') (`pre_mean') (`rkf') (`N')
            }

            drop var3`suffix' var5`suffix' var4`suffix' var6`suffix' var7`suffix'
        }
    }
}

// ------------------------------------------------------------
// 4) Export results
// ------------------------------------------------------------
postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", ///
    replace delimiter(",") quote

di as result "→ Output directory: `result_dir'"
capture log close
