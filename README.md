## Repository Overview

- `data/`           : raw and processed data
- `src/`            : build and configuration scripts
- `spec/`           : individual empirical specifications
- `py/`             : Python utilities for figures and table post-processing

Each specification under `spec/` loads the configuration, builds data if necessary, runs its analysis, and writes outputs.

### Directory Structure

```
project_root/
├── data/
│   ├── raw/          (git-ignored) original data files
│   └── processed/    outputs from the build scripts
│       ├── master_firm.dta
│       └── master_worker.dta
├── src/
│   ├── globals.do            defines global paths (`$raw_data`, `$processed_data`, `$results`)
│   ├── firm_panel.do         build firm-level data
│   └── worker_panel.do       build worker-level data
├── spec/                     Stata analysis scripts
├── py/                       helper Python code
└── results/                  intermediate outputs
```
