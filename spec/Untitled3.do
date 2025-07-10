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
tempfile industries industry_growth industry_growth_yh ///
    company_growth company_growth_yh ///
    msa_growth_yh size_yh ///
    firm_growth

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

*── 3c. INDUSTRY‐growth by half‐year ───────────────────────────────*
preserve
    merge m:1 companyname using `industries', nogenerate
    collapse (last) total_employees covid industry, by(yh companyname)
    encode companyname, gen(company_numeric)
	xtset company_numeric yh
    gen fg = (total_employees/L.total_employees)-1 if _n>1
    winsor2 fg, cuts(1 99) suffix(_we)
    * now average over firms within each industry×yh *
    collapse (mean) fg_we if covid, by(industry yh)
    rename fg_we ind_growth_favg_yh
    save `industry_growth_yh', replace
restore

*── 3d. COMPANY‐growth by half‐year ────────────────────────────────*
preserve
    merge m:1 companyname using `industries', nogenerate
    collapse (last) total_employees covid, by(yh companyname)
    encode companyname, gen(company_numeric)
	xtset company_numeric yh
    gen growth = (total_employees/L.total_employees)-1 if _n>1
    winsor2 growth, cuts(1 99) suffix(_we)
    * now average over that firm×yh *
    collapse (mean) growth_we if covid, by(companyname yh)
    rename growth_we growth_rate_we_post_c_yh
    save `company_growth_yh', replace
restore

*── 3e. MSA‐growth by half‐year ────────────────────────────────────*
preserve
    merge m:1 companyname using `industries', nogenerate
    collapse (last) total_employees covid company_msa, by(yh companyname)
    encode companyname, gen(company_numeric)
	xtset company_numeric yh
    gen fg = (total_employees/L.total_employees)-1 if _n>1
    winsor2 fg, cuts(1 99) suffix(_we)
    * now average over that MSA×yh *
    collapse (mean) fg_we if covid, by(company_msa yh)
    rename fg_we msa_growth_favg_yh
    save `msa_growth_yh', replace
restore


*── 3f. Firm size by half-year ─────────────────────────────────────*
preserve
    // start from the same scoop dataset you used for growth
    import delimited "$processed_data/Scoop_Positions_Firm_Collapse2.csv", clear
    drop v1
    gen date_numeric = date(date, "YMD")
    drop date
    rename date_numeric date
    format date %td

    gen yh = hofd(date)
    format yh %th

    // grab the last head-count in each half-year for each firm
    collapse (last) total_employees, by(yh companyname)
    rename total_employees emp_yh

    save `size_yh', replace
restore


*--------------------------------------------------------------------*
* 3e. Combine for leave-out means & growth bins ---------------------*
*--------------------------------------------------------------------*
use `company_growth_yh', clear   // now one row per firm×yh
merge m:1 companyname using `industries', nogenerate
merge m:1 industry   yh  using `industry_growth_yh', nogenerate
merge m:1 company_msa yh using `msa_growth_yh', nogenerate
merge m:1 companyname yh using `size_yh', nogenerate

*--------------------------------------------------------------------
* Jackknife (leave-one-out) group means for instruments
*--------------------------------------------------------------------

* Leave-one-out industry mean in each yh *
bysort industry yh: egen ind_sum_yh = total(ind_growth_favg_yh)
bysort industry yh: egen ind_n_yh   = count(ind_growth_favg_yh)
gen   avg_ind_yh = (ind_sum_yh - ind_growth_favg_yh) / (ind_n_yh - 1) ///
      if ind_n_yh>1

* Leave-one-out MSA mean in each yh *
bysort company_msa yh: egen msa_sum_yh = total(msa_growth_favg_yh)
bysort company_msa yh: egen msa_n_yh   = count(msa_growth_favg_yh)
gen   avg_msa_yh = (msa_sum_yh - msa_growth_favg_yh)/(msa_n_yh-1) if msa_n_yh>1

	  
egen growth_bin_yh = xtile(growth_rate_we_post_c_yh), by(yh) nq(2)
egen ind_bin_yh    = xtile(avg_ind_yh),                by(yh) nq(2)
egen msa_bin_yh    = xtile(avg_msa_yh),                by(yh) nq(2)
egen size_bin_yh   = xtile(emp_yh),                    by(yh) nq(2)



// capture drop ind_sum_raw ind_n_raw ind_sum_favg ind_n_favg

*--- CREATE the series you'll use in the tile regression -------------
// gen   avg_ind_yh = avg_ind_favg_lo_yh    



// keep companyname growth_rate_we_post_c avg_ind avg_ind_favg_lo avg_msa 

save `firm_growth', replace

*--------------------------------------------------------------------*
* 4) Merge growth info back to user panel    build emp_pre ---------*
*--------------------------------------------------------------------*
use `userpanel', clear                           // reload pristine panel
merge m:1 companyname  yh using `firm_growth', nogenerate



* Remote-growth interactions *
gen postgrow_yh         = growth_bin_yh
gen postgrow_startup_yh = growth_bin_yh * startup

* Industry Bartik shifters *
gen ind_mean_yh         = ind_bin_yh
gen ind_mean_startup_yh = ind_bin_yh * startup

* MSA Bartik shifters *
gen msa_mean_yh         = msa_bin_yh
gen msa_mean_startup_yh = msa_bin_yh * startup

* Size controls *
gen size_covid_yh         = size_bin_yh
gen size_covid_startup_yh = size_bin_yh * startup




*--------------------------------------------------------------------*
* 6) Macro scaffolding for 6 IV columns -----------------------------*
*--------------------------------------------------------------------*
*--------------------------------------------------------------------*
* 6) Macro scaffolding for 6 IV columns -----------------------------*
*--------------------------------------------------------------------*
* Endogenous bundles
local endo1 "var3 var5"
local endo2 "`endo1'"
local endo3 "`endo1'"
* ─ use the half-year growth bins in columns 4–6 ─────────────── *
local endo4 "var3 var5 postgrow_yh postgrow_startup_yh"
local endo5 "`endo4'"
local endo6 "`endo4'"

* Exogenous controls
local exog1 "var4"
local exog2 "`exog1' postgrow_yh postgrow_startup_yh"
local exog3 "`exog2' size_covid_yh size_covid_startup_yh"
local exog4 "`exog1' size_covid_yh size_covid_startup_yh"
local exog5 "`exog4'"
local exog6 "`exog4'"

* Instruments
local zbase "var6 var7"
local zind  "ind_mean_yh ind_mean_startup_yh"
local zmsa  "msa_mean_yh msa_mean_startup_yh"

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

