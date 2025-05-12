
- `data/`           : raw and processed data
- `src/`            : build and configuration scripts
 - `spec/`           : individual empirical specifications
 - `py/`             : Python scripts for generating tables of means and graphs

Each script in `spec/` is self-contained: it loads the configuration, builds the data if needed, reads the master panel, runs its analysis, and writes outputs.

## Directory Structure

project_root/                     
├── data/                        
│   ├── raw/        (git-ignored)  Place original raw data files (CSV, DTA, etc.) here.
│   └── processed/    Outputs of the data build script:
│       ├ master_firm.dta     Cleaned firm-level panel
│       ├ master_worker.dta   Cleaned worker-level panel
│
├── src/                         
│   ├── globals2.do            Defines global macros (`$rawdata`, `$data`, `$results`).
│   ├── build_firm_data.do     Builds firm-level data into `data/processed/master_firm.dta`.
│   └── build_worker_data.do   Builds worker-level data into `data/processed/master_worker.dta`.
│
├── spec/                        
│   ├── company_scaling.do      Stub for the company scaling spec.
│   ├── worker_productivity.do  Stub for worker productivity spec.
│   └── scaling_event.do        Stub for the scaling event-study spec.
│
├── py/                          
└── results/            