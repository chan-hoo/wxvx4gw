#!/usr/bin/env bash

# Read a value from a YAML configuration file.
#
# Usage:
#   read_yaml <config_file> <key_path>
#
# Example:
#   read_yaml config_common.yaml nco_vars.OPS_PATH

read_yaml() {
    local config_file="$1"
    local key_path="$2"

    python3 - "$config_file" "$key_path" <<'PYTHON'
import sys
import yaml

config_file = sys.argv[1]
key_path = sys.argv[2]

try:
    with open(config_file, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    value = config

    for key in key_path.split("."):
        if not isinstance(value, dict) or key not in value:
            sys.exit(f"Error: Configuration key not found: {key_path}")
        value = value[key]

    if value is None:
        print("")
    elif isinstance(value, (dict, list)):
        sys.exit(f"Error: Expected a scalar value for {key_path}")
    else:
        print(value)

except FileNotFoundError:
    sys.exit(f"Error: Configuration file not found: {config_file}")
except yaml.YAMLError as e:
    sys.exit(f"Error: Invalid YAML in {config_file}: {e}")
PYTHON
}
