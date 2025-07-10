*============================================================*
* do/user_remote_growth_specs.do
*  — Six IV columns for remote × startup with growth controls
*============================================================*

capture log close
cap mkdir "log"

*--------------------------------------------------------------------*
* 0) Optional panel variant argument --------------------------------*
*--------------------------------------------------------------------*
args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

local specname "remote_growth_specs_`panel_variant'"
log using "log/`specname'.log", replace text

*--------------------------------------------------------------------*
* 1) Globals & result folder ---------------------------------------*
*--------------------------------------------------------------------*
do "../src/globals.do"                     // defines $processed_data, $results
local result_dir "$results/`specname'"
cap mkdir "`result_dir'"

*--------------------------------------------------------------------*
* 2) Load user panel once ------------------------------------------*
*--------------------------------------------------------------------*
use "$processed_data/user_panel_`panel_variant'.dta", clear
tempfile userpanel
save `userpanel', replace                     // keep a pristine copy

*--------------------------------------------------------------------*
* 3) Create company-level Covid-period growth -----------------------*
*--------------------------------------------------------------------*
tempfile industries industry_growth company_growth firm_growth

* 3a. map companies → industry & MSA
preserve
    collapse (last) industry (last) company_msa, by(companyname)
    keep companyname industry company_msa
    save `industries', replace
restore

* 3b. bring in Scoop head-count file once
import delimited "$processed_data/Scoop_Positions_Firm_Collapse2.csv", clear
drop v1
gen date_numeric = date(date, "YMD")
drop date
rename date_numeric date
format date %td

gen yh = hofd(date)
gen year = yofd(date)
format yh %th

gen byte covid = yh >= 120                 // 2020-H1 and after

*--------------------------------------------------------------------*
* 3c. INDUSTRY-level Covid growth  – create both variants            *
*--------------------------------------------------------------------*
preserve

    merge m:1 companyname using `industries', nogenerate
    collapse (last) total_employees covid industry, by(yh companyname)
    encode companyname, gen(comp_id)
    xtset comp_id yh
    sort  comp_id yh
    gen fg = (total_employees/L.total_employees) - 1 if _n>1
    winsor2 fg, cuts(1 99) suffix(_we)
    collapse (mean) fg_we if covid, by(industry)
    rename  fg_we ind_growth_favg

    

    save `industry_growth', replace
restore


*--------------------------------------------------------------------*
* 3d. COMPANY-level Covid growth ------------------------------------*
*--------------------------------------------------------------------*
preserve
    merge m:1 companyname using `industries', nogenerate
    collapse (last) total_employees covid, by(yh companyname)
    encode companyname, gen(comp_id)
    xtset comp_id yh
    sort  comp_id yh
    gen growth = (total_employees/L.total_employees) - 1 if _n>1
    winsor2 growth, cuts(1 99) suffix(_we)
    collapse (mean) growth_we if covid, by(companyname)
    rename  growth_we growth_rate_we_post_c
    save `company_growth', replace
restore

*--------------------------------------------------------------------*
* 3e. Combine for leave-out means & growth bins ---------------------*
*--------------------------------------------------------------------*
use `company_growth', clear                    // one row per firm
merge m:1 companyname using `industries', nogenerate
merge m:1 industry      using `industry_growth', nogenerate

*--------------------------------------------------------------------
* Jackknife (leave-one-out) group means for instruments
*--------------------------------------------------------------------

* ------------ Jackknife means: FIRM-AVG --------------------------
bysort industry : egen ind_sum_favg = total(ind_growth_favg)
bysort industry : egen ind_n_favg   = count(ind_growth_favg)
gen     avg_ind_favg_lo = (ind_sum_favg - ind_growth_favg)/(ind_n_favg - 1) if ind_n_favg>1


* jackknife leave-one-out MSA mean
bysort company_msa : egen msa_sum = total(growth_rate_we_post_c)
bysort company_msa : egen msa_n   = count(growth_rate_we_post_c)
gen   avg_msa_lo = (msa_sum - growth_rate_we_post_c) / (msa_n - 1) if msa_n>1
drop  msa_sum msa_n



capture drop ind_sum_raw ind_n_raw ind_sum_favg ind_n_favg

*--- CREATE the series you'll use in the tile regression -------------
gen   avg_ind = avg_ind_favg_lo                     

		

// keep companyname growth_rate_we_post_c avg_ind avg_ind_favg_lo avg_msa 

save `firm_growth', replace

*--------------------------------------------------------------------*
* 4) Merge growth info back to user panel  +  build emp_pre ---------*
*--------------------------------------------------------------------*
use `userpanel', clear                           // reload pristine panel
merge m:1 companyname using `firm_growth', nogenerate

*--------------------------------------------------------------------*
* 4a. Create pre-Covid firm size (emp_pre) on the fly ---------------*
*--------------------------------------------------------------------*
tempfile preemp
preserve
    import delimited "$processed_data/Scoop_Positions_Firm_Collapse2.csv", clear
    drop v1
	gen date_numeric = date(date, "YMD")
	drop date
	rename date_numeric date
	format date %td

	gen yh = hofd(date)
	gen year = yofd(date)
	format yh %th
    keep if yh <= 119                               // 2019-H2 and earlier
    collapse (mean) total_employees, by(companyname)
    rename total_employees emp_pre
    save `preemp', replace
restore

merge m:1 companyname using `preemp', nogenerate



*--------------------------------------------------------------------*
* 5) Bin all continuous COVID-period variables into low/high (no if)*
*--------------------------------------------------------------------*
* Note: growth_rate_we_post_c, avg_ind_favg_lo, avg_msa_lo are missing pre-COVID,
*       so xtile automatically ignores those and only bins actual post-COVID obs.

xtile growth_bin = growth_rate_we_post_c, nq(2)
xtile emp_bin    = emp_pre,                nq(2)
xtile ind_bin    = avg_ind_favg_lo,        nq(2)
xtile msa_bin    = avg_msa_lo,             nq(2)

*--------------------------------------------------------------------*
* 6) Build binned regressors & instruments -------------------------*
*--------------------------------------------------------------------*
* postgrow and startup interaction
gen postgrow            = growth_bin
gen postgrow_startup    = growth_bin * startup

* size control
gen size_covid          = emp_bin
gen size_covid_startup  = emp_bin * startup

* industry leave-out instrument
gen ind_mean            = ind_bin
gen ind_mean_startup    = ind_bin * startup

* MSA leave-out instrument
gen msa_mean            = msa_bin
gen msa_mean_startup    = msa_bin * startup


*--------------------------------------------------------------------*
* 6) Macro scaffolding for 6 IV columns -----------------------------*
*--------------------------------------------------------------------*
* Endogenous bundles
local endo1 "var3 var5"
local endo2 "`endo1'"
local endo3 "`endo1'"
local endo4 "`endo1' postgrow postgrow_startup"
local endo5 "`endo4'"
local endo6 "`endo4'"

* Exogenous controls
local exog1 "var4"
local exog2 "`exog1' postgrow postgrow_startup"
local exog3 "`exog2' size_covid size_covid_startup"
local exog4 "`exog1' size_covid size_covid_startup"
local exog5 "`exog4'"
local exog6 "`exog4'"

* Instruments
local zbase "var6 var7"
local zind  "ind_mean ind_mean_startup"
local zmsa  "msa_mean msa_mean_startup"

local instr1 "`zbase'"
local instr2 "`zbase'"
local instr3 "`zbase'"
local instr4 "`zbase' `zind'"
local instr5 "`zbase' `zmsa'"
local instr6 "`zbase' `zind' `zmsa'"

*--------------------------------------------------------------------*
* 7) Estimation loop  ----------------------------------------------*
*--------------------------------------------------------------------*
tempfile results
capture postclose handle
postfile handle ///
    str6   col ///
	str20  param ///
    double coef se pval rkf nobs ///
    using `results', replace

forvalues c = 1/6 {
    di as text "→ Column `c'"
	 local endo  `endo`c''
	 local exog  `exog`c''
	 local instr `instr`c''
    ivreghdfe total_contributions_q100 ///
        (`endo' = `instr') `exog', ///
        absorb(firm_id#user_id yh) ///
        vce(cluster user_id) 

    local rkf = e(rkf)
    local N   = e(N)

    * record baseline coefficients
    foreach v of varlist var3 var5 {
        post handle ("IV`c'") ("`v'") ///
            (_b[`v']) (_se[`v']) ///
            (2*ttail(e(df_r),abs(_b[`v']/_se[`v']))) ///
            (`rkf') (`N')
    }

    * record growth coefficients for columns 4–6
//     if inlist(`c',4,5,6) {
//         foreach v of varlist postgrow postgrow_startup {
//             post handle ("IV`c'") ("`v'") ///
//                 (_b[`v']) (_se[`v']) ///
//                 (2*ttail(e(df_r),abs(_b[`v']/_se[`v']))) ///
//                 (`rkf') (`N')
//         }
//     }
}

postclose handle

use `results', clear
export delimited using "`result_dir'/remote_growth_results.csv", replace
display as result "→ CSV written to `result_dir'/remote_growth_results.csv'"

capture log close

