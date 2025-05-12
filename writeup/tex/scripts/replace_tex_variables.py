#!/usr/bin/env python3
"""
Helper script to replace machine variable names (var3, var4, etc.) in LaTeX
tables (.tex files) under the results directory with their human-readable
definitions parsed from Stata .do scripts in src/, then compile the main
paper document.

Usage:
    python replace_tex_variables.py
"""
import re
from pathlib import Path

def parse_var_defs(do_path):
    """
    Parse Stata .do file to extract lines of the form:
        gen varX = expr
    Returns a dict mapping 'varX' to the RHS expr string.
    """
    var_map = {}
    pattern = re.compile(r"^\s*gen\s+(var\d+)\s*=\s*(.+)$")
    for line in do_path.read_text().splitlines():
        m = pattern.match(line)
        if m:
            var, expr = m.group(1), m.group(2).strip()
            var_map[var] = expr
    return var_map

def latexify(expr):
    """
    Convert a Stata expression like 'remote * covid * startup' into a LaTeX-friendly
    string, e.g. 'remote $\\times$ covid $\\times$ startup', escaping underscores.
    """
    # Escape underscores for LaTeX and split on '*' to insert multiplication signs
    parts = [p.strip().replace('_', r'\_') for p in expr.split('*')]
    # Use raw string for the TeX \times macro to avoid Python escape issues
    return r' $\times$ '.join(parts)

def replace_in_file(tex_path, mapping):
    """
    Read the .tex file, replace all instances of each var in mapping with
    its LaTeXified definition, and overwrite the file.
    """
    text = tex_path.read_text()
    for var, definition in mapping.items():
        # Use a function for replacement to preserve backslashes literally (avoid \t -> tab)
        text = re.sub(rf"\b{var}\b", lambda m, d=definition: d, text)
    tex_path.write_text(text)
    print(f"Updated {tex_path}")

def main():
    # Directories: scripts/, tex/, writeup/, project root
    script_dir = Path(__file__).parent.resolve()           # writeup/tex/scripts
    tex_dir = script_dir.parent                             # writeup/tex
    writeup_dir = tex_dir.parent                            # writeup
    project_root = writeup_dir.parent                       # project root

    # Parse variable definitions
    firm_defs = parse_var_defs(project_root / 'src' / 'firm_panel.do')
    worker_defs = parse_var_defs(project_root / 'src' / 'worker_panel.do')
    # Convert to LaTeX-friendly form
    firm_map = {v: latexify(expr) for v, expr in firm_defs.items()}
    worker_map = {v: latexify(expr) for v, expr in worker_defs.items()}
    # DEBUG: print mappings to verify \times usage
    print("Firm variable mappings:")
    for var in sorted(firm_map):
        print(f"  {var} -> {firm_map[var]}")
    print("Worker variable mappings:")
    for var in sorted(worker_map):
        print(f"  {var} -> {worker_map[var]}")

    # Replace in all .tex under results
    results_dir = project_root / 'results'
    for sub in results_dir.iterdir():
        if not sub.is_dir():
            continue
        mapping = firm_map if sub.name.startswith('firm') else (
                  worker_map if sub.name.startswith('worker') else None)
        if mapping is None:
            continue
        for tex_file in sub.rglob('*.tex'):
            replace_in_file(tex_file, mapping)


if __name__ == '__main__':
    main()