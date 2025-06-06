#!/bin/bash
# Submit each productivity specification and panel variant as a separate Slurm job.
# This mirrors spec/run_productivity_variants.do but runs each combination in parallel.

set -euo pipefail

# Determine repository root (directory above this script)
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

EMAIL="sxr203@nyu.edu"

# Folder to store generated sbatch files and slurm outputs
SBATCH_DIR="hpc/sbatch"
OUT_DIR="hpc/out"
LOG_DIR="spec/log"

mkdir -p "$SBATCH_DIR" "$OUT_DIR" "$LOG_DIR"

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
    script_base="$(basename "$script" .do)"
    job_name="${script_base}_${variant}"
    sbatch_file="${SBATCH_DIR}/${job_name}.sbatch"

    cat >"$sbatch_file" <<EOF
#!/bin/bash
#SBATCH --job-name=${job_name}
#SBATCH --output=${OUT_DIR}/${job_name}.out
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=${EMAIL}
#SBATCH --time=48:00:00
#SBATCH --mem=128G
#SBATCH --cpus-per-task=4

set -euo pipefail
cd "$ROOT_DIR"

module purge
module load stata/17.0

stata -b do spec/${script} ${variant}

if [ -f spec/${script_base}.log ]; then
    mv spec/${script_base}.log ${LOG_DIR}/${job_name}.log
fi
EOF

    sbatch "$sbatch_file"
  done
done

