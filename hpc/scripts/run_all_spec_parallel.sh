#!/bin/bash
# Orchestrate end-to-end submission of all spec/*.do analyses on Slurm.
# Builds necessary firm and user panels, then submits regressions with dependencies.

set -euo pipefail

# Repository root – adjust if your checkout lives elsewhere
REPO="$HOME/main"

EMAIL="sxr203@nyu.edu"

# Where to write the generated sbatch wrapper files
SBATCH_DIR="$REPO/hpc/sbatch"
mkdir -p "$SBATCH_DIR"

# -----------------------------------------------------------------------------
# Lists of specification scripts to run (define **before** first use because 
# the script is executed with `set -u`, which treats undefined variables as
# errors).
# -----------------------------------------------------------------------------

# Firm-level specifications
FIRM_SCRIPTS=(
    firm_event_study.do
    firm_scaling_initial.do
    firm_scaling.do
    firm_scaling_alternative_fe.do
    firm_mechanisms_lean.do
    firm_mechanisms.do
    firm_remote_first_stage.do
)

# User-level specifications and panel variants
VARIANTS=(unbalanced balanced precovid balanced_pre)
USER_SCRIPTS=(
    user_productivity.do
    user_productivity_alternative_fe.do
    user_productivity_initial.do
    user_mechanisms.do
    user_mechanisms_lean.do
)

echo "Submitting panel-building jobs..."
# Build firm panel
FIRM_PANEL_JID=$(sbatch --parsable "$SBATCH_DIR/build_firm_panel.sbatch")
echo "  build_firm_panel job ID: $FIRM_PANEL_JID"
# Build user panels
USER_PANEL_JID=$(sbatch --parsable "$SBATCH_DIR/build_all_user_panels.sbatch")
echo "  build_all_user_panels job ID: $USER_PANEL_JID"

echo
echo "Generating sbatch files for firm regression jobs..."
for script in "${FIRM_SCRIPTS[@]}"; do
    base="${script%.do}"
    sbatch_file="$SBATCH_DIR/${base}.sbatch"
    cat >"$sbatch_file" <<EOF
#!/bin/bash
#SBATCH --time=2:00:00
#SBATCH --mem=10GB
#SBATCH --job-name=${base}
#SBATCH --output=${base}.out
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=${EMAIL}

set -euo pipefail
cd "$HOME/main/spec"

module purge
module load stata/17.0

stata -b do ${script}
EOF
done

# Submit the firm-level regression jobs, all depending on the firm panel build.
echo "Submitting firm regression jobs (dependent on firm panel)..."
for script in "${FIRM_SCRIPTS[@]}"; do
    base="${script%.do}"
    job_name="$base"
    sbatch_file="${SBATCH_DIR}/${job_name}.sbatch"
    sbatch --dependency=afterok:${FIRM_PANEL_JID} "$sbatch_file"
    echo "  Submitted $job_name (after firm panel: $FIRM_PANEL_JID)"
done

echo
echo "Generating sbatch files for user regression jobs..."
for variant in "${VARIANTS[@]}"; do
  for script in "${USER_SCRIPTS[@]}"; do
    script_base="${script%.do}"
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
  done
done

# Submit the user-level regression jobs, all depending on successful user panel build.
echo "Submitting user regression jobs (dependent on user panels)..."
for variant in "${VARIANTS[@]}"; do
    for script in "${USER_SCRIPTS[@]}"; do
        script_base="${script%.do}"
        job_name="${script_base}_${variant}"
        sbatch_file="${SBATCH_DIR}/${job_name}.sbatch"
        sbatch --dependency=afterok:${USER_PANEL_JID} "$sbatch_file"
        echo "  Submitted $job_name (after user panels: $USER_PANEL_JID)"
    done
done

echo "All spec jobs submitted. Monitor with 'squeue -u \$USER' and inspect .out files."
echo "All spec jobs submitted. Monitor with 'squeue -u \$USER' and inspect .out files."