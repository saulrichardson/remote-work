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
        local __bslash = char(92)
        local __cwd = subinstr("`c(pwd)'", "`__bslash'", "/", .)
        if fileexists("`__cwd'/spec/00_paths.do") {
            global PROJECT_ROOT "`__cwd'"
        }
        else {
            local __self "`c(filename)'"
            if "`__self'" == "" {
                local __self "`c(pwd)'/spec/00_paths.do"
            }

            local __normalized = subinstr("`__self'", "`__bslash'", "/", .)
            local __spec_suffix "/spec/00_paths.do"
            local __spec_len = length("`__spec_suffix'")
            local __tail = substr("`__normalized'", max(1, length("`__normalized'") - `__spec_len' + 1), .)

            if "`__tail'" == "`__spec_suffix'" {
                local __root = substr("`__normalized'", 1, length("`__normalized'") - `__spec_len')
            }
            else {
                local __slash = strrpos("`__normalized'", "/")
                if `__slash' <= 0 {
                    di as error "00_paths.do: unable to determine project root."
                    exit 198
                }
                local __root = substr("`__normalized'", 1, `__slash' - 1)
            }
            global PROJECT_ROOT "`__root'"
        }
    }
}

if "$PROJECT_ROOT" == "" {
    di as error "00_paths.do: PROJECT_ROOT is empty."
    exit 198
}

global raw_data        "$PROJECT_ROOT/data/raw"
global clean_data      "$PROJECT_ROOT/data/clean"
global processed_data  "$clean_data"
global results         "$PROJECT_ROOT/results/raw"
global LOG_DIR         "$PROJECT_ROOT/log"

capture quietly mkdir "$LOG_DIR"
capture quietly mkdir "$clean_data"
