#!/usr/bin/env bash

if [ -z "${ECF_HOST}" ]; then
  export ECF_HOST=$(hostname)
fi
if [ -z "${ECF_PORT}" ]; then
  export ECF_PORT=$(( $(id -u) + 1500 ))
fi
export ECF_HOME="{{ exp_ecf_path }}"

echo "ECF_HOME: ${ECF_HOME}"
echo "ECF_PORT: ${ECF_PORT}"
echo "ECF_HOST: ${ECF_HOST}"

# Find path to ecFlow bin directory
ecflow_bin_path=$(ecflow_start.sh -h 2>&1 \
      | awk '/^Usage:/ {
              path=$2
              sub("/ecflow_start.sh$", "", path)
              print path
            }')
if [ -z "${ecflow_bin_path}" ]; then
  echo "FATAL ERROR: ecflow_start.sh is not found. ecFlow module may not be loaded properly."
  exit 1
else
  echo "ecFlow BIN directory: ${ecflow_bin_path}"
fi

# Run ecFlow module built-in start script
${ecflow_bin_path}/ecflow_start.sh -d ${ECF_HOME} -p ${ECF_PORT}
