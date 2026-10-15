#!/usr/bin/env bash

export ECF_PORT=$(( $(id -u) + 1500 ))

# Find path to ecFlow bin directory
ecflow_bin_path=$(ecflow_stop.sh -h 2>&1 \
      | awk '/^Usage:/ {
              path=$2
              sub("/ecflow_stop.sh$", "", path)
              print path
            }')
if [ -z "${ecflow_bin_path}" ]; then
  echo "FATAL ERROR: ecflow_stop.sh is not found. ecFlow module may not be loaded properly."
  exit 1
else
  echo "ecFlow BIN directory: ${ecflow_bin_path}"
fi

# Run ecFlow module built-in stop script
${ecflow_bin_path}/ecflow_stop.sh -p ${ECF_PORT}

