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

*====================================================================*
*  Extract first-stage growth residualization regression
*====================================================================*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

do "../globals.do"

*--------------------------------------------------------------------*
* Reconstruct the data exactly as in main analysis
*--------------------------------------------------------------------*
import delimited "$processed_data/Scoop_Positions_Firm_Collapse2.csv", clear
drop v1
gen date_numeric = date(date, "YMD")
drop date
rename date_numeric date
format date %td
gen yh = hofd(date)
format yh %th
drop if date == 22797
collapse (last) total_employees date (sum) join leave, by(companyname yh)
gen byte covid = (yh >= 120)

* Get growth rate
preserve
    encode companyname, gen(firm_n)
    xtset firm_n yh
    sort firm_n yh
    gen growth_yh = (total_employees / L.total_employees) - 1 if _n>1
    winsor2 growth_yh, cuts(1 99) suffix(_we)
    collapse (mean) growth_yh_we if covid, by(companyname)
    rename growth_yh_we growth_rate_we_post_c
    tempfile g_postavg
    save `g_postavg'
restore

* Get firm keys
preserve
    use "$processed_data/firm_panel.dta", clear
    keep companyname industry
    gen company_msa = "all"  // placeholder
    bysort companyname: keep if _n == 1
    tempfile firmkeys
    save `firmkeys'
restore

* Get firm controls
preserve
    use "$processed_data/firm_panel.dta", clear
    keep companyname rent hhi_1000 covid startup
    gen companyname_c = lower(companyname)
    collapse (last) startup (last) rent (last) hhi_1000 if covid, by(companyname_c)
    xtile tile_rent = rent, nq(2)
    xtile tile_hhi = hhi_1000, nq(2)
    tempfile firm_extra
    save `firm_extra'
restore

* Build leave-one-out growth
merge m:1 companyname using `firmkeys', nogenerate
encode companyname, gen(firm_n)
xtset firm_n yh
sort firm_n yh
gen fg = (total_employees/L.total_employees) - 1 if _n>1
winsor2 fg, cuts(1 99) suffix(_we)
keep if covid
tempfile postcovid
save `postcovid'

* Industry leave-one-out
use `postcovid', clear
bys industry: egen ind_sum = total(fg_we)
bys industry: egen ind_N = count(fg_we)
gen ind_growth_postavg_lo = (ind_sum - fg_we) / (ind_N - 1) if ind_N > 1
collapse (mean) ind_growth_postavg_lo, by(industry)
tempfile ind_postavg
save `ind_postavg'

* MSA leave-one-out
use `postcovid', clear
bys company_msa: egen msa_sum = total(fg_we)
bys company_msa: egen msa_N = count(fg_we)
gen msa_growth_postavg_lo = (msa_sum - fg_we) / (msa_N - 1) if msa_N > 1
keep company_msa msa_growth_postavg_lo
collapse (mean) msa_growth_postavg_lo, by(company_msa)
tempfile msa_postavg
save `msa_postavg'

* Merge everything for first-stage regression
use `postcovid', clear
gen companyname_c = lower(companyname)
merge m:1 industry using `ind_postavg', keep(match) nogen
merge m:1 company_msa using `msa_postavg', keep(match) nogen
merge m:1 companyname using `g_postavg', keep(match) nogen
merge m:1 companyname_c using `firm_extra', keep(match) nogen

* Run and save first-stage regression
eststo clear
eststo: reg growth_rate_we_post_c ind_growth_postavg_lo msa_growth_postavg_lo tile_rent tile_hhi

* Export results
esttab using "$results/first_stage_growth_residualization.tex", ///
    replace booktabs ///
    b(3) se(3) ///
    star(* 0.10 ** 0.05 *** 0.01) ///
    label ///
    title("First-Stage: Growth Residualization") ///
    mtitle("Dep Var: Firm Growth Rate") ///
    addnote("Growth rate is average post-COVID employment growth." ///
            "Industry and MSA growth are leave-one-out means." ///
            "Rent and HHI tiles are binary (above/below median).") ///
    r2 ar2 obs

* Also save a cleaner version
outreg2 using "$results/first_stage_clean", ///
    tex(fragment) replace ///
    label dec(3) ///
    title("First-Stage Regression: Firm Growth Residualization") ///
    addnote("Dependent variable: Average post-COVID firm employment growth rate." ///
            "All variables measured at the firm level.")
            
di "First-stage regression results saved"