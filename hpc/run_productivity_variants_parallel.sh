#!/bin/bash
# Submit each productivity specification and panel variant as a separate Slurm job.
# This mirrors spec/run_productivity_variants.do but runs each combination in parallel.

set -euo pipefail

# Determine repository root (directory above this script)
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Adjust path to Stata executable if needed
STATA_BIN="stata-mp"
EMAIL="sxr203@nyu.edu"

variants=(unbalanced balanced precovid)
scripts=(
    user_productivity.do
    user_productivity_alternative_fe.do
    user_productivity_initial.do
    user_mechanisms.do
    user_mechanisms_lean.do
)

for variant in "${variants[@]}"; do
  for script in "${scripts[@]}"; do
    job_name="$(basename "$script" .do)_${variant}"
    sbatch <<EOT
#!/bin/bash
#SBATCH --job-name=${job_name}
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=${EMAIL}
#SBATCH --time=48:00:00
#SBATCH --mem=128G
#SBATCH --cpus-per-task=4

set -euo pipefail
cd "$ROOT_DIR"

"${STATA_BIN}" -b do spec/${script} ${variant}
EOT
  done
done

