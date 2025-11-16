* ----------------------------------------------------------------------
* 00_paths.do — Central path definitions for the WFH Startups project
* Source this once per Stata session to expose PROJECT_ROOT + helpers.
* ----------------------------------------------------------------------

capture confirm global PROJECT_ROOT
if _rc | "$PROJECT_ROOT" == "" {
    local __env_root: env PROJECT_ROOT
    if "`__env_root'" != "" {
        global PROJECT_ROOT "`__env_root'"
    }
    else {
        local __self "`c(filename)'"
        if "`__self'" == "" {
            local __self "`c(pwd)'/00_paths.do"
        }

        local __bslash = char(92)
        local __normalized = subinstr("`__self'", "`__bslash'", "/", .)
        local __slash = strrpos("`__normalized'", "/")
        if `__slash' <= 0 {
            di as error "00_paths.do: unable to determine project root."
            exit 198
        }
        local __root = substr("`__normalized'", 1, `__slash' - 1)
        global PROJECT_ROOT "`__root'"
    }
}

if "$PROJECT_ROOT" == "" {
    di as error "00_paths.do: PROJECT_ROOT is empty."
    exit 198
}

global RAW_DATA        "$PROJECT_ROOT/data/raw"
global CLEAN_DATA      "$PROJECT_ROOT/data/clean"
global PROCESSED_DATA  "$CLEAN_DATA"
global RAW_RESULTS     "$PROJECT_ROOT/results/raw"
global FINAL_TEX       "$PROJECT_ROOT/results/cleaned/tex"
global FINAL_FIGURES   "$PROJECT_ROOT/results/cleaned/figures"
global LOG_DIR         "$PROJECT_ROOT/log"

global DIR_DATA        "$RAW_DATA"
global DIR_PROCESSED   "$PROCESSED_DATA"
global DIR_CLEAN       "$CLEAN_DATA"
global DIR_RESULTS     "$RAW_RESULTS"
global DIR_FINAL_TEX   "$FINAL_TEX"
global DIR_FINAL_FIGS  "$FINAL_FIGURES"
global DIR_LOG         "$LOG_DIR"
global DIR_DO          "$PROJECT_ROOT/spec/stata"
global DIR_SRC         "$PROJECT_ROOT/src/stata"

global results        "$RAW_RESULTS"
global processed_data "$PROCESSED_DATA"
global clean_data     "$CLEAN_DATA"
global data_processed "$PROCESSED_DATA"
global clean_results  "$PROJECT_ROOT/results/cleaned"

capture quietly mkdir "$LOG_DIR"
capture quietly mkdir "$CLEAN_DATA"
