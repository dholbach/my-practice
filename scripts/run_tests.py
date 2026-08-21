#!/usr/bin/env python
"""Quick test runner that writes summary to /tmp/summary.txt"""

import subprocess
import sys

args = sys.argv[1:] if len(sys.argv) > 1 else []
cmd = ["python", "manage.py", "test", "--keepdb"] + args

r = subprocess.run(cmd, capture_output=True, text=True, cwd="/app")
combined = r.stdout + r.stderr
lines = combined.splitlines()

summary_lines = [
    line
    for line in lines
    if any(k in line for k in ("FAIL:", "ERROR:", "Ran ", "OK", "FAILED", "Preserving"))
]
summary = "\n".join(summary_lines)

with open("/tmp/summary.txt", "w") as f:
    f.write(summary)
    f.write(f"\nReturn code: {r.returncode}\n")

print(summary)
print(f"Return code: {r.returncode}")
