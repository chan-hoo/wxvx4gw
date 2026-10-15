#!/usr/bin/env bash

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 --suspend | --resume | --kill | --halt | --restart"
  exit 1
fi
ACTION="$1"

if [ -z "${ECF_HOST}" ]; then
  export ECF_HOST=$(hostname)
fi
if [ -z "${ECF_PORT}" ]; then
  export ECF_PORT=$(( $(id -u) + 1500 ))
fi
export ECF_HOME="{{ exp_case_path }}/ecf"
export ECF_SUITE="{{ exp_case_name }}"

echo "ECF_HOME: ${ECF_HOME}"
echo "ECF_PORT: ${ECF_PORT}"
echo "ECF_HOST: ${ECF_HOST}"
echo "ECF_SUITE: ${ECF_SUITE}"

if [ "${ACTION}" = "--suspend" ]; then
  # Suspend the given node. This prevents job generation for the given node, or any child node.
  echo "Suspend suite ${ECF_SUITE} ..."
  ecflow_client --port="${ECF_PORT}" --host="${ECF_HOST}" --suspend "/${ECF_SUITE}"
elif [ "${ACTION}" = "--resume" ]; then
  # Resume the given node. This allows job generation for the given node, or any child node.
  echo "Resume suite ${ECF_SUITE} ..."
  ecflow_client --port="${ECF_PORT}" --host="${ECF_HOST}" --resume "/${ECF_SUITE}"
elif [ "${ACTION}" = "--kill" ]; then
  # Kills the job associated with the node.
  echo "Kill suite ${ECF_SUITE} ..."
  ecflow_client --port="${ECF_PORT}" --host="${ECF_HOST}" --kill "/${ECF_SUITE}"
########## Server control ##########
elif [ "${ACTION}" = "--halt" ]; then
  # Stop server communication with jobs, and new job scheduling.
  echo "Halt server ..."
  ecflow_client --port="${ECF_PORT}" --host="${ECF_HOST}" --halt=yes
elif [ "${ACTION}" = "--restart" ]; then
  # Start job scheduling, communication with jobs, and respond to all requests.
  echo "Restart server ..."
  ecflow_client --port="${ECF_PORT}" --host="${ECF_HOST}" --restart
else
  echo "FATAL ERROR: ${ACTION} is NOT supported in this script. Please check --help"
  ecflow_client --help=summary
  exit 2
fi
