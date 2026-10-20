#!/usr/bin/env python3

import os
import shutil
import subprocess
from pathlib import Path
import yaml

# Read configuration YAML file
path_to_config = Path(os.environ["exp_config_dir"])
config_file = path_to_config / "config.yaml"
with config_file.open("r") as f:
    config = yaml.safe_load(f)

# Extract parameter values
path_to_ops = Path(config["path_to_ops"])
environment = config["environment"]
cycle = config["cycle"]

print(f"path_to_ops: {path_to_ops}")
print(f"environment: {environment}")
print(f"cycle: {cycle}")


# Run wxvx

wxvx_executable = shutil.which("wxvx")

if wxvx_executable is None:
    raise FileNotFoundError(
        "Cannot find 'wxvx'. Check that the wxvx environment is activated."
    )

command = [
    wxvx_executable,
    "-c", "wxvx-grid2grid-global.yaml",
    "-t", "plots",
    "-f",
]

result = subprocess.run(command, check=False)

if result.returncode == 0:
    Path("runscript.wxvx-grid2grid-global.done").touch()
else:
    raise subprocess.CalledProcessError(result.returncode, command)
