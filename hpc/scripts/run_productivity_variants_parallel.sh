#!/bin/bash
# Submit each productivity specification and panel variant as a separate Slurm job.
# This mirrors spec/run_productivity_variants.do but runs each combination in parallel.

set -euo pipefail

# Repository root
REPO="$HOME/main"
cd "$REPO"

EMAIL="sxr203@nyu.edu"

# Folder to store generated sbatch files and slurm outputs
SBATCH_DIR="$REPO/hpc/sbatch"
mkdir -p "$SBATCH_DIR"

variants=(unbalanced balanced precovid balanced_pre)
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
    sbatch_file="$SBATCH_DIR/${job_name}.sbatch"

    cat >"$sbatch_file" <<EOF
#!/bin/bash
#SBATCH --time=3:00:00
#SBATCH --mem=10GB
#SBATCH --job-name=${job_name}
#SBATCH --output=${job_name}.out
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=${EMAIL}

set -euo pipefail
cd "$HOME/main/spec"

module purge
module load stata/17.0

    stata -b do ${script} ${variant}
EOF

    if [[ -n "${USER_PANEL_JID:-}" ]]; then
      sbatch --dependency=afterok:${USER_PANEL_JID} "$sbatch_file"
    else
      sbatch "$sbatch_file"
    fi
  done
done

