*============================================================*
* user_productivity_llm_equity_mechanism_battery.do
*
* Goal:
*   Systematically test a broad (but econometrically-motivated) battery of
*   transformations of the LLM "equity offered" signal to see whether adding
*   equity controls attenuates the baseline Remote×Post×Startup coefficient
*   (var5) in the pair-FE user productivity design.
*
* Key conventions:
*   - Backfill-only: missing/unobserved equity fields are coded as 0.
*   - No "parsable vs non-parsable" missingness controls in the regressions.
*
* Software-firm restriction:
*   - Runs the same battery on:
*       (i) full sample,
*      (ii) Technology industry (industry_id == 20),
*     (iii) NAICS software definitions (mirrors user_productivity_tech_filters.do):
*           - NAICS 5415xx computer systems design / custom programming
*           - NAICS 5112xx software publishers (when available)
*
* Output:
*   results/raw/user_productivity_llm_equity_mechanism_battery_<panel_variant>/consolidated_results.csv
*============================================================*

		args panel_variant enriched_panel_csv fe_mode run_mode
		if "`panel_variant'" == "" local panel_variant "precovid"
		if "`fe_mode'" == "" local fe_mode "pair"
		if "`run_mode'" == "" local run_mode "full"

* 0) Setup environment
local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}
do "`__bootstrap'"

* Note: Stata's command-line argument parsing can drop truly-empty arguments.
* To request the default enriched panel path, pass `default` (or `.`) as the
* second argument instead of an empty string.
if "`enriched_panel_csv'" == "" | inlist(lower("`enriched_panel_csv'"), ".", "default") {
    local enriched_panel_csv "$results/postings_description_equity/firm_merge/latest_firm_yh_llm_equity_enriched.csv"
}
capture confirm file "`enriched_panel_csv'"
if _rc {
    di as error "Missing enriched LLM equity panel: `enriched_panel_csv'"
    exit 601
}

	*------------------------------------------------------------*
	* FE mode (pair FE vs baseline FE)
	*------------------------------------------------------------*
	if "`fe_mode'" == "pair" {
	    local specname "user_productivity_llm_equity_mechanism_battery_`panel_variant'"
	    local FE "absorb(firm_id#user_id yh) vce(cluster user_id)"
	}
	else if "`fe_mode'" == "baseline" {
	    local specname "user_productivity_llm_equity_mechanism_battery_baselinefe_`panel_variant'"
	    local FE "absorb(user_id firm_id yh) vce(cluster user_id)"
	}
	else {
	    di as error "Unknown fe_mode: `fe_mode'. Expected 'pair' or 'baseline'."
	    exit 198
	}
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text

*------------------------------------------------------------*
* 1) Load enriched firm×yh panel and merge into user panel
*------------------------------------------------------------*
tempfile llm_by_firm

preserve
import delimited using "`enriched_panel_csv'", clear varnames(1)

	* Columns required for the battery (raw + strict + higher-coverage intensity proxies)
	keep firm_id_key yh ///
	    llm_equity_any_raw llm_equity_share_parse_ok_raw llm_equity_count_parse_ok_raw ///
	    llm_equity_any_strict llm_equity_share_parse_ok_strict llm_equity_count_parse_ok_strict ///
	    llm_equity_any_software_strict ///
	    n_llm_target_postings llm_n_parse_ok_raw llm_n_equity_true_raw llm_n_equity_true_strict ///
	    n_postings_desc_total n_keyword_hit_candidates

	rename firm_id_key __firm_name_key
	rename yh __yh_key
	replace __firm_name_key = lower(trim(__firm_name_key))
	replace __firm_name_key = "" if inlist(__firm_name_key, ".", "", "nan", "none")

	foreach v in ///
	    llm_equity_any_raw llm_equity_share_parse_ok_raw llm_equity_count_parse_ok_raw ///
	    llm_equity_any_strict llm_equity_share_parse_ok_strict llm_equity_count_parse_ok_strict ///
	    llm_equity_any_software_strict ///
	    n_llm_target_postings llm_n_parse_ok_raw llm_n_equity_true_raw llm_n_equity_true_strict ///
	    n_postings_desc_total n_keyword_hit_candidates {
	    capture destring `v', replace force
	}

* Backfill=0 at firm×yh before merging
	foreach v in ///
	    llm_equity_any_raw llm_equity_share_parse_ok_raw llm_equity_count_parse_ok_raw ///
	    llm_equity_any_strict llm_equity_share_parse_ok_strict llm_equity_count_parse_ok_strict ///
	    llm_equity_any_software_strict ///
	    n_llm_target_postings llm_n_parse_ok_raw llm_n_equity_true_raw llm_n_equity_true_strict ///
	    n_postings_desc_total n_keyword_hit_candidates {
	    replace `v' = 0 if missing(`v')
	}

replace llm_equity_any_raw = 0 if llm_equity_any_raw < 0 | llm_equity_any_raw > 1
replace llm_equity_any_strict = 0 if llm_equity_any_strict < 0 | llm_equity_any_strict > 1
replace llm_equity_any_software_strict = 0 if llm_equity_any_software_strict < 0 | llm_equity_any_software_strict > 1

replace llm_equity_share_parse_ok_raw = 0 if llm_equity_share_parse_ok_raw < 0 | llm_equity_share_parse_ok_raw > 1
replace llm_equity_share_parse_ok_strict = 0 if llm_equity_share_parse_ok_strict < 0 | llm_equity_share_parse_ok_strict > 1

replace llm_equity_count_parse_ok_raw = 0 if llm_equity_count_parse_ok_raw < 0
replace llm_equity_count_parse_ok_strict = 0 if llm_equity_count_parse_ok_strict < 0

	replace n_llm_target_postings = 0 if n_llm_target_postings < 0
	replace llm_n_parse_ok_raw = 0 if llm_n_parse_ok_raw < 0
	replace llm_n_equity_true_raw = 0 if llm_n_equity_true_raw < 0
	replace llm_n_equity_true_strict = 0 if llm_n_equity_true_strict < 0
	replace n_postings_desc_total = 0 if n_postings_desc_total < 0
	replace n_keyword_hit_candidates = 0 if n_keyword_hit_candidates < 0

	drop if missing(__firm_name_key) | missing(__yh_key)
	duplicates drop __firm_name_key __yh_key, force
save `llm_by_firm', replace
restore

	use "$processed_data/user_panel_`panel_variant'.dta", clear
	gen str244 __firm_name_key = lower(trim(companyname))
	replace __firm_name_key = "" if inlist(__firm_name_key, ".", "", "nan", "none")
	gen str10 __yh_key = string(dofh(yh), "%tdCCYY-NN-DD")
	
	merge m:1 __firm_name_key __yh_key using `llm_by_firm', keep(master match) nogen

	* Backfill=0 after merge for safety
	foreach v in ///
	    llm_equity_any_raw llm_equity_share_parse_ok_raw llm_equity_count_parse_ok_raw ///
	    llm_equity_any_strict llm_equity_share_parse_ok_strict llm_equity_count_parse_ok_strict ///
	    llm_equity_any_software_strict ///
	    n_llm_target_postings llm_n_parse_ok_raw llm_n_equity_true_raw llm_n_equity_true_strict ///
	    n_postings_desc_total n_keyword_hit_candidates {
	    replace `v' = 0 if missing(`v')
	}

*------------------------------------------------------------*
* 2) Build equity measures + transformations (raw + strict)
*------------------------------------------------------------*
* Cell-level (firm×yh) base measures
gen double eq_any_raw_fh   = llm_equity_any_raw
gen double eq_share_raw_fh = llm_equity_share_parse_ok_raw
gen double eq_count_raw_fh = llm_equity_count_parse_ok_raw

gen double eq_any_str_fh   = llm_equity_any_strict
gen double eq_share_str_fh = llm_equity_share_parse_ok_strict
gen double eq_count_str_fh = llm_equity_count_parse_ok_strict

foreach v in ///
    eq_any_raw_fh eq_share_raw_fh eq_count_raw_fh ///
    eq_any_str_fh eq_share_str_fh eq_count_str_fh {
    replace `v' = 0 if missing(`v')
}

* Bounds
replace eq_any_raw_fh = 0 if eq_any_raw_fh < 0 | eq_any_raw_fh > 1
replace eq_any_str_fh = 0 if eq_any_str_fh < 0 | eq_any_str_fh > 1
replace eq_share_raw_fh = 0 if eq_share_raw_fh < 0 | eq_share_raw_fh > 1
replace eq_share_str_fh = 0 if eq_share_str_fh < 0 | eq_share_str_fh > 1
replace eq_count_raw_fh = 0 if eq_count_raw_fh < 0
replace eq_count_str_fh = 0 if eq_count_str_fh < 0

* Count transforms (econometric motivation: skew / diminishing returns)
gen double eq_countlog_raw_fh   = ln(1 + eq_count_raw_fh)
gen double eq_countasinh_raw_fh = asinh(eq_count_raw_fh)
gen double eq_countsqrt_raw_fh  = sqrt(eq_count_raw_fh)

gen double eq_countlog_str_fh   = ln(1 + eq_count_str_fh)
gen double eq_countasinh_str_fh = asinh(eq_count_str_fh)
gen double eq_countsqrt_str_fh  = sqrt(eq_count_str_fh)

* Share transforms (econometric motivation: proportions in [0,1])
gen double eq_shareasin_raw_fh = asin(sqrt(eq_share_raw_fh))
gen double eq_shareasin_str_fh = asin(sqrt(eq_share_str_fh))

	local __eps = 0.001
	gen double eq_sharelogit_raw_fh = ln((eq_share_raw_fh + `__eps') / (1 - eq_share_raw_fh + `__eps'))
	gen double eq_sharelogit_str_fh = ln((eq_share_str_fh + `__eps') / (1 - eq_share_str_fh + `__eps'))
	
	*------------------------------------------------------------*
	* Additional intensity proxies (higher-coverage; still backfill=0)
	*   1) Keyword-hit intensity among *all* postings (proxy; not LLM-based)
	*   2) LLM equity share using denominators that treat unparsed as 0
	*      - among all keyword-hit candidates (denom = n_llm_target_postings)
	*      - among all postings (denom = n_postings_desc_total)
	*------------------------------------------------------------*
	
	gen double kw_hits_fh = n_keyword_hit_candidates
	replace kw_hits_fh = 0 if missing(kw_hits_fh) | kw_hits_fh < 0
	gen byte kw_any_fh = (kw_hits_fh > 0)
	replace kw_any_fh = 0 if missing(kw_any_fh)
	
	gen double kw_share_fh = cond(n_postings_desc_total > 0, kw_hits_fh / n_postings_desc_total, 0)
	replace kw_share_fh = 0 if missing(kw_share_fh) | kw_share_fh < 0
	replace kw_share_fh = 1 if kw_share_fh > 1
	
	gen double eq_share_cand_raw_fh = cond(n_llm_target_postings > 0, llm_n_equity_true_raw / n_llm_target_postings, 0)
	gen double eq_share_cand_str_fh = cond(n_llm_target_postings > 0, llm_n_equity_true_strict / n_llm_target_postings, 0)
	foreach v in eq_share_cand_raw_fh eq_share_cand_str_fh {
	    replace `v' = 0 if missing(`v') | `v' < 0
	    replace `v' = 1 if `v' > 1
	}
	
	gen double eq_share_postings_raw_fh = cond(n_postings_desc_total > 0, llm_n_equity_true_raw / n_postings_desc_total, 0)
	gen double eq_share_postings_str_fh = cond(n_postings_desc_total > 0, llm_n_equity_true_strict / n_postings_desc_total, 0)
	foreach v in eq_share_postings_raw_fh eq_share_postings_str_fh {
	    replace `v' = 0 if missing(`v') | `v' < 0
	    replace `v' = 1 if `v' > 1
	}

	* Short aliases (Stata varname limit is 32 chars; keep aggregates compact)
	gen double r_any    = eq_any_raw_fh
	gen double r_shr    = eq_share_raw_fh
	gen double r_shasin = eq_shareasin_raw_fh
	gen double r_shlogit= eq_sharelogit_raw_fh
	gen double r_clog   = eq_countlog_raw_fh
	gen double r_casinh = eq_countasinh_raw_fh
	gen double r_csqrt  = eq_countsqrt_raw_fh

gen double s_any    = eq_any_str_fh
gen double s_shr    = eq_share_str_fh
gen double s_shasin = eq_shareasin_str_fh
	gen double s_shlogit= eq_sharelogit_str_fh
	gen double s_clog   = eq_countlog_str_fh
	gen double s_casinh = eq_countasinh_str_fh
	gen double s_csqrt  = eq_countsqrt_str_fh
	
	* Keyword-hit intensity (count + share + transforms)
	gen double k_cnt    = kw_hits_fh
	gen double k_clog   = ln(1 + k_cnt)
	gen double k_casinh = asinh(k_cnt)
	gen double k_csqrt  = sqrt(k_cnt)
	gen double k_any    = kw_any_fh
	gen double k_shr    = kw_share_fh
	gen double k_shas   = asin(sqrt(k_shr))
	gen double k_shlg   = ln((k_shr + `__eps') / (1 - k_shr + `__eps'))
	
	* LLM equity shares with backfill denominators (candidates vs all postings)
	gen double r_shc    = eq_share_cand_raw_fh
	gen double r_shcas  = asin(sqrt(r_shc))
	gen double r_shclg  = ln((r_shc + `__eps') / (1 - r_shc + `__eps'))
	gen double s_shc    = eq_share_cand_str_fh
	gen double s_shcas  = asin(sqrt(s_shc))
	gen double s_shclg  = ln((s_shc + `__eps') / (1 - s_shc + `__eps'))
	
	gen double r_shp    = eq_share_postings_raw_fh
	gen double r_shpas  = asin(sqrt(r_shp))
	gen double r_shplg  = ln((r_shp + `__eps') / (1 - r_shp + `__eps'))
	gen double s_shp    = eq_share_postings_str_fh
	gen double s_shpas  = asin(sqrt(s_shp))
	gen double s_shplg  = ln((s_shp + `__eps') / (1 - s_shp + `__eps'))

*------------------------------------------------------------*
* 3) Firm-level aggregations (pre/post means; post max; delta)
*------------------------------------------------------------*
	tempvar __tag_fy
	egen byte `__tag_fy' = tag(firm_id yh)
	
	* Software-firm flags (NAICS-based; mirrors user_productivity_tech_filters.do)
	tempvar __naics6_num __naics2 __naics4
	capture confirm numeric variable naics6
	if !_rc {
	    gen double `__naics6_num' = naics6
	}
	else {
	    destring naics6, gen(`__naics6_num') force
	}
	replace `__naics6_num' = . if `__naics6_num' <= 0
	gen int `__naics2' = floor(`__naics6_num'/10000) if `__naics6_num' < .
	gen int `__naics4' = floor(`__naics6_num'/100) if `__naics6_num' < .
	
	gen byte soft_naics5415 = inlist(`__naics4', 5415) | inlist(`__naics6_num', 541511, 541512, 541513, 541514, 541519)
	replace soft_naics5415 = 0 if missing(soft_naics5415)
	
	gen byte soft_naics5112 = inlist(`__naics4', 5112) | inlist(`__naics6_num', 511210)
	replace soft_naics5112 = 0 if missing(soft_naics5112)
	
	gen byte soft_naics_any = (soft_naics5415 == 1 | soft_naics5112 == 1)
	replace soft_naics_any = 0 if missing(soft_naics_any)

	* Helper: firm-level post max + post mean + pre mean + delta for a list of cell measures
	foreach base in ///
	    r_any r_shr r_shasin r_shlogit r_clog r_casinh r_csqrt ///
	    s_any s_shr s_shasin s_shlogit s_clog s_casinh s_csqrt ///
	    k_any k_shr k_shas k_shlg k_clog k_casinh k_csqrt ///
	    r_shc r_shcas r_shclg s_shc s_shcas s_shclg ///
	    r_shp r_shpas r_shplg s_shp s_shpas s_shplg {

    gen double __`base'_post = `base' if `__tag_fy' == 1 & covid == 1
    gen double __`base'_pre  = `base' if `__tag_fy' == 1 & covid == 0

    bysort firm_id: egen double `base'_firm_post = mean(__`base'_post)
    bysort firm_id: egen double `base'_firm_pre  = mean(__`base'_pre)
    bysort firm_id: egen double `base'_firm_post_max = max(__`base'_post)

    replace `base'_firm_post = 0 if missing(`base'_firm_post)
    replace `base'_firm_pre  = 0 if missing(`base'_firm_pre)
    replace `base'_firm_post_max = 0 if missing(`base'_firm_post_max)

    gen double `base'_firm_delta = `base'_firm_post - `base'_firm_pre
    replace `base'_firm_delta = 0 if missing(`base'_firm_delta)

    drop __`base'_post __`base'_pre
}

	* "New equity offer" (raw + strict): no any-pre (mean==0) and some any-post (post max==1)
	gen byte r_any_firm_new = (r_any_firm_pre == 0 & r_any_firm_post_max == 1)
	replace r_any_firm_new = 0 if missing(r_any_firm_new)
	gen byte s_any_firm_new = (s_any_firm_pre == 0 & s_any_firm_post_max == 1)
	replace s_any_firm_new = 0 if missing(s_any_firm_new)
	
	* Firm-level ever indicators (time-invariant): any equity signal in any half-year
	bysort firm_id: egen byte r_any_firm_ever = max(r_any)
	replace r_any_firm_ever = 0 if missing(r_any_firm_ever)
	bysort firm_id: egen byte s_any_firm_ever = max(s_any)
	replace s_any_firm_ever = 0 if missing(s_any_firm_ever)

* Quantile bins of post-period raw/strict share (computed on one row per firm)
tempvar __tag_firm __tile_q4 __tile_q5 __tile_q10
egen byte `__tag_firm' = tag(firm_id)

	xtile `__tile_q4'  = r_shr_firm_post if `__tag_firm' == 1, nq(4)
	xtile `__tile_q5'  = r_shr_firm_post if `__tag_firm' == 1, nq(5)
	xtile `__tile_q10' = r_shr_firm_post if `__tag_firm' == 1, nq(10)
gen byte r_share_topq4 = (`__tile_q4' == 4) if `__tag_firm' == 1
gen byte r_share_topq5 = (`__tile_q5' == 5) if `__tag_firm' == 1
gen byte r_share_topd10 = (`__tile_q10' == 10) if `__tag_firm' == 1
foreach v in r_share_topq4 r_share_topq5 r_share_topd10 {
    replace `v' = 0 if missing(`v')
    bysort firm_id: egen byte __`v'_firm = max(`v')
    drop `v'
    rename __`v'_firm `v'
}
drop `__tile_q4' `__tile_q5' `__tile_q10'

xtile `__tile_q4'  = s_shr_firm_post if `__tag_firm' == 1, nq(4)
xtile `__tile_q5'  = s_shr_firm_post if `__tag_firm' == 1, nq(5)
xtile `__tile_q10' = s_shr_firm_post if `__tag_firm' == 1, nq(10)
gen byte s_share_topq4 = (`__tile_q4' == 4) if `__tag_firm' == 1
gen byte s_share_topq5 = (`__tile_q5' == 5) if `__tag_firm' == 1
gen byte s_share_topd10 = (`__tile_q10' == 10) if `__tag_firm' == 1
foreach v in s_share_topq4 s_share_topq5 s_share_topd10 {
    replace `v' = 0 if missing(`v')
    bysort firm_id: egen byte __`v'_firm = max(`v')
    drop `v'
    rename __`v'_firm `v'
}
drop `__tile_q4' `__tile_q5' `__tile_q10'

* Threshold indicators on post share (raw + strict)
gen byte r_share_ge10 = (r_shr_firm_post >= 0.10)
gen byte r_share_ge25 = (r_shr_firm_post >= 0.25)
gen byte r_share_ge50 = (r_shr_firm_post >= 0.50)
gen byte s_share_ge10 = (s_shr_firm_post >= 0.10)
gen byte s_share_ge25 = (s_shr_firm_post >= 0.25)
gen byte s_share_ge50 = (s_shr_firm_post >= 0.50)
foreach v in r_share_ge10 r_share_ge25 r_share_ge50 s_share_ge10 s_share_ge25 s_share_ge50 {
    replace `v' = 0 if missing(`v')
}

	* Percentile ranks of post share (raw + strict) on [0,1]
	* NOTE: Avoid `unique` ranks (which break ties arbitrarily and can inject
	* spurious variation when many firms have identical shares, especially 0).
	tempvar __rank
	
	egen double `__rank' = rank(r_shr_firm_post) if `__tag_firm' == 1 & r_shr_firm_post > 0
	summarize `__rank' if `__tag_firm' == 1 & r_shr_firm_post > 0, meanonly
	local __rank_max = r(max)
	gen double r_share_post_rank = cond(`__tag_firm' == 1 & r_shr_firm_post > 0 & `__rank_max' > 1, (`__rank' - 1) / (`__rank_max' - 1), 0)
	replace r_share_post_rank = 0 if missing(r_share_post_rank)
	bysort firm_id: egen double __r_rank_firm = max(r_share_post_rank)
	drop r_share_post_rank
	rename __r_rank_firm r_share_post_rank
	drop `__rank'
	
	egen double `__rank' = rank(s_shr_firm_post) if `__tag_firm' == 1 & s_shr_firm_post > 0
	summarize `__rank' if `__tag_firm' == 1 & s_shr_firm_post > 0, meanonly
	local __rank_max = r(max)
	gen double s_share_post_rank = cond(`__tag_firm' == 1 & s_shr_firm_post > 0 & `__rank_max' > 1, (`__rank' - 1) / (`__rank_max' - 1), 0)
	replace s_share_post_rank = 0 if missing(s_share_post_rank)
	bysort firm_id: egen double __s_rank_firm = max(s_share_post_rank)
	drop s_share_post_rank
	rename __s_rank_firm s_share_post_rank
	drop `__rank'

drop `__tag_firm'

* Map discrete/rank variants into exp_* names for a uniform control generator below
gen double exp_r_share_topq4     = r_share_topq4
gen double exp_r_share_topq5     = r_share_topq5
gen double exp_r_share_topd10    = r_share_topd10
gen double exp_r_share_ge10      = r_share_ge10
gen double exp_r_share_ge25      = r_share_ge25
gen double exp_r_share_ge50      = r_share_ge50
gen double exp_r_share_post_rank = r_share_post_rank

gen double exp_s_share_topq4     = s_share_topq4
gen double exp_s_share_topq5     = s_share_topq5
gen double exp_s_share_topd10    = s_share_topd10
gen double exp_s_share_ge10      = s_share_ge10
gen double exp_s_share_ge25      = s_share_ge25
gen double exp_s_share_ge50      = s_share_ge50
gen double exp_s_share_post_rank = s_share_post_rank

	*------------------------------------------------------------*
	* 4) Define battery variants as post-shift controls
	*    Each variant v uses controls: covid*exposure(v) and covid*exposure(v)*startup
	*------------------------------------------------------------*
	* Cell-level (firm×half-year) exposures
	gen double exp_r_any_cell    = r_any
	gen double exp_r_shr_cell    = r_shr
	gen double exp_r_shasin_cell = r_shasin
	gen double exp_r_shlogit_cell= r_shlogit
	gen double exp_r_clog_cell   = r_clog
	
	gen double exp_s_any_cell    = s_any
	gen double exp_s_shr_cell    = s_shr
	gen double exp_s_shasin_cell = s_shasin
	gen double exp_s_shlogit_cell= s_shlogit
	gen double exp_s_clog_cell   = s_clog
	
	* Raw firm-level exposures
	gen double exp_r_any_post        = r_any_firm_post_max
	gen double exp_r_any_ever        = r_any_firm_ever
	gen double exp_r_any_pre         = (r_any_firm_pre > 0)
	replace exp_r_any_pre = 0 if missing(exp_r_any_pre)
	gen double exp_r_any_new         = r_any_firm_new
	gen double exp_r_share_post      = r_shr_firm_post
	gen double exp_r_share_post_max  = r_shr_firm_post_max
	gen double exp_r_share_post_asin = r_shasin_firm_post
	gen double exp_r_share_post_logit= r_shlogit_firm_post
	gen double exp_r_share_delta     = r_shr_firm_delta
	gen double exp_r_countlog_post   = r_clog_firm_post
	gen double exp_r_countasinh_post = r_casinh_firm_post
	gen double exp_r_countsqrt_post  = r_csqrt_firm_post
	gen double exp_r_countlog_delta  = r_clog_firm_delta
	
	* Strict firm-level exposures
	gen double exp_s_any_post        = s_any_firm_post_max
	gen double exp_s_any_ever        = s_any_firm_ever
	gen double exp_s_any_new         = s_any_firm_new
	gen double exp_s_share_post      = s_shr_firm_post
	gen double exp_s_share_post_max  = s_shr_firm_post_max
	gen double exp_s_share_post_asin = s_shasin_firm_post
	gen double exp_s_share_post_logit= s_shlogit_firm_post
	gen double exp_s_share_delta     = s_shr_firm_delta
	gen double exp_s_countlog_post   = s_clog_firm_post
	gen double exp_s_countasinh_post = s_casinh_firm_post
	gen double exp_s_countsqrt_post  = s_csqrt_firm_post
	gen double exp_s_countlog_delta  = s_clog_firm_delta
	
	* Keyword-hit intensity (cell + firm aggregates)
	gen double exp_k_any_cell    = k_any
	gen double exp_k_shr_cell    = k_shr
	gen double exp_k_shas_cell   = k_shas
	gen double exp_k_shlg_cell   = k_shlg
	gen double exp_k_clog_cell   = k_clog
	
	gen byte k_any_firm_new = (k_any_firm_pre == 0 & k_any_firm_post_max == 1)
	replace k_any_firm_new = 0 if missing(k_any_firm_new)
	
	gen double exp_k_any_post    = k_any_firm_post_max
	gen double exp_k_any_new     = k_any_firm_new
	gen double exp_k_shr_post    = k_shr_firm_post
	gen double exp_k_shas_post   = k_shas_firm_post
	gen double exp_k_shlg_post   = k_shlg_firm_post
	gen double exp_k_shr_delta   = k_shr_firm_delta
	gen double exp_k_clog_post   = k_clog_firm_post
	
	* LLM equity shares with backfill denominators (candidates vs all postings)
	gen double exp_r_shc_cell    = r_shc
	gen double exp_r_shcas_cell  = r_shcas
	gen double exp_r_shclg_cell  = r_shclg
	gen double exp_r_shc_post    = r_shc_firm_post
	gen double exp_r_shcas_post  = r_shcas_firm_post
	gen double exp_r_shclg_post  = r_shclg_firm_post
	gen double exp_r_shc_delta   = r_shc_firm_delta
	
	gen double exp_s_shc_cell    = s_shc
	gen double exp_s_shcas_cell  = s_shcas
	gen double exp_s_shclg_cell  = s_shclg
	gen double exp_s_shc_post    = s_shc_firm_post
	gen double exp_s_shcas_post  = s_shcas_firm_post
	gen double exp_s_shclg_post  = s_shclg_firm_post
	gen double exp_s_shc_delta   = s_shc_firm_delta
	
	gen double exp_r_shp_cell    = r_shp
	gen double exp_r_shpas_cell  = r_shpas
	gen double exp_r_shplg_cell  = r_shplg
	gen double exp_r_shp_post    = r_shp_firm_post
	gen double exp_r_shpas_post  = r_shpas_firm_post
	gen double exp_r_shplg_post  = r_shplg_firm_post
	gen double exp_r_shp_delta   = r_shp_firm_delta
	
	gen double exp_s_shp_cell    = s_shp
	gen double exp_s_shpas_cell  = s_shpas
	gen double exp_s_shplg_cell  = s_shplg
	gen double exp_s_shp_post    = s_shp_firm_post
	gen double exp_s_shpas_post  = s_shpas_firm_post
	gen double exp_s_shplg_post  = s_shplg_firm_post
	gen double exp_s_shp_delta   = s_shp_firm_delta
	
	* Software-strict (cell-level indicator)
	gen double exp_w_any_post    = llm_equity_any_software_strict
	
	foreach v in ///
	    r_any_cell r_shr_cell r_shasin_cell r_shlogit_cell r_clog_cell ///
	    s_any_cell s_shr_cell s_shasin_cell s_shlogit_cell s_clog_cell ///
	    r_any_post r_any_ever r_any_pre r_any_new r_share_post r_share_post_max r_share_post_asin r_share_post_logit r_share_delta ///
	    r_countlog_post r_countasinh_post r_countsqrt_post r_countlog_delta ///
	    s_any_post s_any_ever s_any_new s_share_post s_share_post_max s_share_post_asin s_share_post_logit s_share_delta ///
	    s_countlog_post s_countasinh_post s_countsqrt_post s_countlog_delta ///
	    k_any_cell k_shr_cell k_shas_cell k_shlg_cell k_clog_cell ///
	    k_any_post k_any_new k_shr_post k_shas_post k_shlg_post k_shr_delta k_clog_post ///
	    r_shc_cell r_shcas_cell r_shclg_cell r_shc_post r_shcas_post r_shclg_post r_shc_delta ///
	    s_shc_cell s_shcas_cell s_shclg_cell s_shc_post s_shcas_post s_shclg_post s_shc_delta ///
	    r_shp_cell r_shpas_cell r_shplg_cell r_shp_post r_shpas_post r_shplg_post r_shp_delta ///
	    s_shp_cell s_shpas_cell s_shplg_cell s_shp_post s_shpas_post s_shplg_post s_shp_delta ///
	    w_any_post ///
	    r_share_topq4 r_share_topq5 r_share_topd10 r_share_ge10 r_share_ge25 r_share_ge50 r_share_post_rank ///
	    s_share_topq4 s_share_topq5 s_share_topd10 s_share_ge10 s_share_ge25 s_share_ge50 s_share_post_rank {

    gen double z_`v'    = covid * exp_`v'
    gen double z_`v'_su = covid * exp_`v' * startup
}

*------------------------------------------------------------*
* 5) Regression loop (pair FE; OLS + IV)
*------------------------------------------------------------*
local outcome "total_contributions_q100"
summarize `outcome' if covid == 0, meanonly
local pre_mean = r(mean)

	local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

capture postclose handle
tempfile out
postfile handle ///
    str8  model_type ///
    str16 sample_mode ///
    str32 spec_variant ///
    str40 outcome ///
    str40 param ///
    double coef se pval pre_mean ///
    double rkf nobs ///
    using `out', replace

	local spec_variants_full ///
	    baseline ///
	    r_any_cell r_shr_cell r_shasin_cell r_shlogit_cell r_clog_cell ///
	    s_any_cell s_shr_cell s_shasin_cell s_shlogit_cell s_clog_cell ///
	    r_any_post r_any_ever r_any_pre r_any_new r_share_post r_share_post_max r_share_post_asin r_share_post_logit r_share_delta ///
	    r_countlog_post r_countasinh_post r_countsqrt_post r_countlog_delta ///
	    s_any_post s_any_ever s_any_new s_share_post s_share_post_max s_share_post_asin s_share_post_logit s_share_delta ///
	    s_countlog_post s_countasinh_post s_countsqrt_post s_countlog_delta ///
	    k_any_cell k_shr_cell k_shas_cell k_shlg_cell k_clog_cell ///
	    k_any_post k_any_new k_shr_post k_shas_post k_shlg_post k_shr_delta k_clog_post ///
	    r_shc_cell r_shcas_cell r_shclg_cell r_shc_post r_shcas_post r_shclg_post r_shc_delta ///
	    s_shc_cell s_shcas_cell s_shclg_cell s_shc_post s_shcas_post s_shclg_post s_shc_delta ///
	    r_shp_cell r_shpas_cell r_shplg_cell r_shp_post r_shpas_post r_shplg_post r_shp_delta ///
	    s_shp_cell s_shpas_cell s_shplg_cell s_shp_post s_shpas_post s_shplg_post s_shp_delta ///
	    w_any_post ///
	    r_share_topq4 r_share_topq5 r_share_topd10 r_share_ge10 r_share_ge25 r_share_ge50 r_share_post_rank ///
	    s_share_topq4 s_share_topq5 s_share_topd10 s_share_ge10 s_share_ge25 s_share_ge50 s_share_post_rank
	
	local sample_modes_full "all tech20 soft5415 soft5112 softany"

	* Optional short run (for quick FE comparisons).
	local spec_variants "`spec_variants_full'"
	local sample_modes "`sample_modes_full'"
	if "`run_mode'" == "k_any_only" {
	    local spec_variants "baseline k_any_post"
	    local sample_modes "all"
	}
	else if "`run_mode'" == "all_only" {
	    local spec_variants "`spec_variants_full'"
	    local sample_modes "all"
	}
	else if "`run_mode'" == "focused_horse_race" {
	    local spec_variants ///
	        baseline ///
	        r_any_ever ///
	        r_shp_post ///
	        r_countlog_post ///
	        r_share_topq5 ///
	        s_share_topq5 ///
	        k_any_post ///
	        k_clog_post ///
	        w_any_post
	    local sample_modes "all"
	}
	else if "`run_mode'" == "k_any_and_r_shp_post" {
	    local spec_variants "baseline k_any_post r_shp_post"
	    local sample_modes "all"
	}
	else if "`run_mode'" == "r_any_ever_and_r_shp_post" {
	    local spec_variants "baseline r_any_ever r_shp_post"
	    local sample_modes "all"
	}
	else if "`run_mode'" == "r_any_pre_only" {
	    local spec_variants "baseline r_any_pre"
	    local sample_modes "all"
	}
	else if "`run_mode'" != "full" {
	    di as error "Unknown run_mode: `run_mode'. Expected 'full', 'all_only', 'focused_horse_race', 'k_any_only', 'k_any_and_r_shp_post', 'r_any_ever_and_r_shp_post', or 'r_any_pre_only'."
	    exit 198
	}

foreach sample_mode of local sample_modes {
    preserve

	    if "`sample_mode'" == "tech20" {
	        keep if industry_id == 20
	    }
	    else if "`sample_mode'" == "soft5415" {
	        keep if soft_naics5415 == 1
	    }
	    else if "`sample_mode'" == "soft5112" {
	        keep if soft_naics5112 == 1
	    }
	    else if "`sample_mode'" == "softany" {
	        keep if soft_naics_any == 1
	    }

    foreach spec_variant of local spec_variants {
        local controls ""
        if "`spec_variant'" != "baseline" {
            local controls "z_`spec_variant' z_`spec_variant'_su"
        }

        local ols_rhs "var3 var5 var4 `controls'"
        local iv_endo "var3 var5"
        local iv_inst "var6 var7"
        local iv_exog "var4 `controls'"

        * OLS
        capture quietly reghdfe `outcome' `ols_rhs', `FE'
        if !_rc {
            local nobs = e(N)
            local __post_params "var3 var5 var4"
            if "`spec_variant'" != "baseline" {
                local __post_params "`__post_params' z_`spec_variant' z_`spec_variant'_su"
            }
            foreach p of local __post_params {
                local b  = _b[`p']
                local se = _se[`p']
                local pval = .
                if `se' < . & `se' != 0 & e(df_r) < . {
                    local t = `b'/`se'
                    local pval = 2*ttail(e(df_r), abs(`t'))
                }
                post handle ("OLS") ("`sample_mode'") ("`spec_variant'") ("`outcome'") ("`p'") ///
                    (`b') (`se') (`pval') (`pre_mean') (.) (`nobs')
            }
        }

        * IV
        capture quietly ivreghdfe `outcome' (`iv_endo' = `iv_inst') `iv_exog', `FE'
        if !_rc {
            local nobs = e(N)
            local rkf = .
            capture local rkf = e(rkf)
            local __post_params "var3 var5 var4"
            if "`spec_variant'" != "baseline" {
                local __post_params "`__post_params' z_`spec_variant' z_`spec_variant'_su"
            }
            foreach p of local __post_params {
                local b  = _b[`p']
                local se = _se[`p']
                local pval = .
                if `se' < . & `se' != 0 & e(df_r) < . {
                    local t = `b'/`se'
                    local pval = 2*ttail(e(df_r), abs(`t'))
                }
                post handle ("IV") ("`sample_mode'") ("`spec_variant'") ("`outcome'") ("`p'") ///
                    (`b') (`se') (`pval') (`pre_mean') (`rkf') (`nobs')
            }
        }
    }

    restore
}

postclose handle
use `out', clear
	export delimited using "`result_dir'/consolidated_results.csv", replace delimiter(",") quote
	di as result "→ CSV : `result_dir'/consolidated_results.csv"

log close
