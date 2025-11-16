capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/build_worker_modal_role.log", replace text

use "$data/expanded_half_years_2.dta", clear

keep if yh < 120                    
keep user_id role_k7 

* choose the modal (most frequent) pre-COVID role for each worker
bysort user_id role_k7: gen _freq = _N
gsort  user_id -_freq role_k7
bysort user_id: keep if _n == 1
rename role_k7 baseline_role_k7
label var baseline_role_k7 "Worker's modal role up to 2019"

keep user_id baseline_role_k7

tempfile worker_baseline_role
save "$processed_data/worker_baseline_role", replace

log close
