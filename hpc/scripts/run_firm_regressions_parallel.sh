#!/bin/bash
# Submit each firm-specification regression as a separate Slurm job.
# Mirrors spec/*.do files for firm regressions.

set -euo pipefail

# Repository root for convenience (not exported)
REPO="$HOME/main"
cd "$REPO"

EMAIL="sxr203@nyu.edu"

# Directories for generated sbatch files and slurm outputs
SBATCH_DIR="$REPO/hpc/sbatch"
mkdir -p "$SBATCH_DIR"

# List of firm-specification do-files to run
scripts=(
    firm_event_study.do
    firm_scaling_initial.do
    firm_scaling.do
    firm_scaling_alternative_fe.do
    firm_mechanisms_lean.do
    firm_mechanisms.do
    firm_remote_first_stage.do
)

for script in "${scripts[@]}"; do
    base="$(basename "$script" .do)"
    job_name="$base"
    sbatch_file="$SBATCH_DIR/${job_name}.sbatch"

    cat >"$sbatch_file" <<EOF
#!/bin/bash
#SBATCH --time=2:00:00
#SBATCH --mem=10GB
#SBATCH --job-name=${job_name}
#SBATCH --output=${job_name}.out
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=${EMAIL}

set -euo pipefail
cd "$HOME/main/spec"

module purge
module load stata/17.0

stata -b do $script
EOF

    if [[ -n "${FIRM_PANEL_JID:-}" ]]; then
        sbatch --dependency=afterok:${FIRM_PANEL_JID} "$sbatch_file"
    else
        sbatch "$sbatch_file"
    fi
done
