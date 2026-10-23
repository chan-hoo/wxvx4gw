#!/usr/bin/env python3
"""
Generate task-specific WXVX configuration files.

Read config_base.yaml, combine the parameter groups specified for
each task, and write flattened config_[task].yaml files.

Expected input structure:

    parm/
    ├── config_base.yaml
    ├── config_platform.yaml
    └── setup.py

Usage:
    python setup.py
    python setup.py --config config_base.yaml
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any
from copy import deepcopy
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, StrictUndefined

import yaml


# ---------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s::L%(lineno)d::%(message)s",
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------
# datetime format
# ---------------------------------------------------------------------

def format_datetime(value):
    """Format a date as YYYY-MM-DD HH:MM:SS."""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")

    if isinstance(value, str):
        # Accept both T and space separators.
        return datetime.fromisoformat(value).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    raise TypeError(
        f"Expected datetime or string, got {type(value).__name__}"
    )

# ---------------------------------------------------------------------
# Configuration generator
# ---------------------------------------------------------------------

class ConfigGenerator:
    """Generate flattened YAML configuration files for WXVX tasks."""

    # -----------------------------------------------------------------
    # Initialize
    # -----------------------------------------------------------------

    def __init__(self, config_file, *args, **kwargs):
        """
        Initialize the configuration generator.
    
        Parameters
        ----------
        config_file : str or pathlib.Path
            Path to config_base.yaml. Relative paths are resolved
            relative to the directory containing this script.
        """
        self.script_dir = Path(__file__).resolve().parent
    
        config_file = Path(config_file).expanduser()
    
        if not config_file.is_absolute():
            config_file = self.script_dir / config_file
    
        self.config_file = config_file.resolve()
    
        # The wxvx4gw repository root is the parent of parm/.
        self.repo_dir = self.script_dir.parent
    
        # Experiment cases directory under the parm directory.
        self.exp_cases_dir = self.script_dir / "exp_cases"
    
        # Default OPS directory under the parm directory.
        self.default_ops_path = self.repo_dir / "parm" / "PTMP"
    
        self.config: dict[str, Any] = {}
        self.platform_config: dict[str, Any] = {}
        self.platform_params: dict[str, Any] = {}

    # -----------------------------------------------------------------
    # Read the base configuration
    # -----------------------------------------------------------------

    def load_config(self) -> dict[str, Any]:
        """Load and validate config_base.yaml."""
        if not self.config_file.is_file():
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_file}"
            )

        logger.info("Reading configuration: %s", self.config_file)

        with self.config_file.open("r", encoding="utf-8") as stream:
            config = yaml.safe_load(stream)

        if not isinstance(config, dict):
            raise ValueError(
                "config_base.yaml must contain a YAML mapping at "
                "the top level."
            )

        if "tasks" not in config:
            raise ValueError(
                "Missing required 'tasks' group in config_base.yaml."
            )

        if not isinstance(config["tasks"], dict):
            raise ValueError(
                "The 'tasks' group must be a mapping of task names "
                "to lists of parameter group names."
            )

        self.config = config

        task_list = self.config.get("task_list", [])
        
        logger.info(
            "Found %d selected task(s) out of %d defined task(s).",
            len(task_list),
            len(self.config["tasks"]),
        )

        return self.config

    # -----------------------------------------------------------------
    # Validate selected tasks
    # -----------------------------------------------------------------

    def validate_task_list(self) -> list[str]:
        """Validate and return the tasks selected for this experiment."""

        task_list = self.config.get("task_list")

        if not isinstance(task_list, list) or not task_list:
            raise ValueError(
                "'task_list' must be a non-empty list of task names."
            )

        tasks = self.config["tasks"]

        for task_name in task_list:
            if not isinstance(task_name, str) or not task_name.strip():
                raise ValueError(
                    f"Invalid task name in 'task_list': {task_name!r}"
                )

            if task_name not in tasks:
                raise ValueError(
                    f"Task '{task_name}' is listed in 'task_list' "
                    "but is not defined in 'tasks'."
                )

        if len(task_list) != len(set(task_list)):
            raise ValueError(
                "'task_list' contains duplicate task names."
            )

        return task_list

    # -----------------------------------------------------------------
    # Read plotform-specific configuration
    # -----------------------------------------------------------------

    def load_config_platform(self):
        """Load platform-specific parameters from config_platform.yaml."""
    
        platform_config_path = self.script_dir / "config_platform.yaml"
    
        if not platform_config_path.is_file():
            raise FileNotFoundError(
                f"Platform configuration not found: {platform_config_path}"
            )
    
        with platform_config_path.open("r", encoding="utf-8") as f:
            self.platform_config = yaml.safe_load(f) or {}
    
        platform = self.config.get("app", {}).get("platform")
    
        if not isinstance(platform, str) or not platform.strip():
            raise ValueError(
                "Missing or invalid 'platform' in the 'app' group "
                "of config_base.yaml."
            )
    
        platform = platform.strip().lower()
        platforms = self.platform_config.get("platforms", {})
    
        if platform not in platforms:
            supported = ", ".join(sorted(platforms))
            raise ValueError(
                f"Unsupported platform '{platform}'. "
                f"Supported platforms: {supported}"
            )
    
        self.platform_params = platforms[platform]

        return self.platform_params

    # -----------------------------------------------------------------
    # Recursively merge group parameters
    # -----------------------------------------------------------------

    def deep_merge(
        self,
        target: dict,
        source: dict,
    ) -> dict:
        """
        Recursively merge source into target without modifying source.
    
        - Preserve parameters that exist only in either dictionary.
        - Recursively merge nested dictionaries.
        - If the same parameter exists in both dictionaries,
          the value from source takes precedence.
        - Deep-copy assigned values to prevent shared references.
        """
        for key, value in source.items():
            if (
                key in target
                and isinstance(target[key], dict)
                and isinstance(value, dict)
            ):
                self.deep_merge(target[key], value)
            else:
                target[key] = deepcopy(value)
    
        return target

    # -----------------------------------------------------------------
    # Determine the output directory
    # -----------------------------------------------------------------

    def get_output_dir(self) -> Path:
        """
        Determine the output directory using app.exp_case_name.

        Expected path:
            wxvx4gw/../exp_cases/<exp_case_name>/config/
        """
        if "app" not in self.config:
            raise ValueError(
                "Missing required 'app' parameter group."
            )

        app_config = self.config["app"]

        if not isinstance(app_config, dict):
            raise ValueError(
                "The 'app' group must be a mapping."
            )

        exp_case_name = app_config.get("exp_case_name")

        if not isinstance(exp_case_name, str) or not exp_case_name.strip():
            raise ValueError(
                "'exp_case_name' must be a non-empty string "
                "in the 'app' group."
            )

        exp_case_name = exp_case_name.strip()

        # Prevent absolute paths and directory traversal.
        case_name_path = Path(exp_case_name)

        if (
            case_name_path.is_absolute()
            or len(case_name_path.parts) != 1
            or exp_case_name in {".", ".."}
        ):
            raise ValueError(
                f"Invalid exp_case_name: {exp_case_name!r}"
            )

        output_dir = (
            self.exp_cases_dir
            / exp_case_name
            / "configs"
        )

        output_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Output directory: %s", output_dir)

        return output_dir

    # -----------------------------------------------------------------
    # Build a flattened configuration for one task
    # -----------------------------------------------------------------

    def build_task_config(
        self,
        task_name: str,
        group_names: list[str],
        hpc_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Build a flattened configuration for a task.
    
        Special handling:
          - common: add metadata.
          - prewxvx: generate frequency, lead time, dates, and variables.
          - plot_vx_grid / plot_vx_obs: transform common configuration
            into plotting parameters.
        """
        if not isinstance(group_names, list):
            raise ValueError(
                f"Task '{task_name}' must specify a list of "
                "parameter group names."
            )

        task_config: dict[str, Any] = {}
        
        if hpc_params is None:
            hpc_params = {}

        def merge_groups(
            names: list[str],
            target: dict[str, Any],
            visited: set[str] | None = None,
        ) -> None:
            """Recursively expand and merge configuration groups."""
    
            if visited is None:
                visited = set()
    
            for group_name in names:
                if not isinstance(group_name, str):
                    raise ValueError(
                        f"Task '{task_name}' contains an invalid "
                        f"group name: {group_name!r}"
                    )
    
                if group_name == "tasks":
                    raise ValueError(
                        f"Task '{task_name}' must not include "
                        "'tasks' as a parameter group."
                    )
    
                if group_name not in self.config:
                    raise ValueError(
                        f"Task '{task_name}' references the undefined "
                        f"parameter group '{group_name}'."
                    )
    
                group_config = self.config[group_name]
    
                if isinstance(group_config, list):
                    if group_name in visited:
                        raise ValueError(
                            "Circular configuration reference detected "
                            f"for group '{group_name}' in task "
                            f"'{task_name}'."
                        )
    
                    merge_groups(
                        group_config,
                        target,
                        visited | {group_name},
                    )
    
                elif isinstance(group_config, dict):
                    self.deep_merge(target, group_config)
    
                else:
                    raise ValueError(
                        f"Configuration group '{group_name}' must be "
                        "a dictionary or a list of group names."
                    )
    
        # -------------------------------------------------------------
        # Exclude common for tasks that require transformed parameters.
        # -------------------------------------------------------------
        special_tasks = {
            "prewxvx",
            "plot_vx_grid",
            "plot_vx_obs",
        }
    
        if task_name in special_tasks:
            group_names = [
                group for group in group_names
                if group != "common"
            ]

        # Merge the remaining task configuration groups.
        merge_groups(group_names, task_config)

        # -------------------------------------------------------------
        # Add task metadata to config_common.yaml.
        # -------------------------------------------------------------
        if task_name == "common":
            # Add external_data flags for selected tasks.
            for name in self.validate_task_list():
                definition = self.config["tasks"][name]
                task_config[f"external_data_{name}"] = definition.get(
                    "external_data", False
                )
    
        # -------------------------------------------------------------
        # Generate transformed parameters for special tasks.
        # -------------------------------------------------------------
        if task_name in special_tasks:
            common = self.config.get("common", {})
    
            cycles = common.get("cycles", {})
            leadtimes = common.get("leadtimes", {})
            variables = common.get("variables", {})
    
            # =========================================================
            # prewxvx
            # =========================================================
            if task_name == "prewxvx":
    
                # Forecast frequency: '6:00:00' -> '6h'.
                leadtime_step = leadtimes.get("step")
    
                if leadtime_step is not None:
                    if (
                        isinstance(leadtime_step, str)
                        and ":" in leadtime_step
                    ):
                        hours = int(leadtime_step.split(":")[0])
                        task_config["freq"] = f"{hours}h"
                    else:
                        task_config["freq"] = leadtime_step
    
                # Maximum forecast lead time: '24' -> 24.
                leadtime_stop = leadtimes.get("stop")
    
                if leadtime_stop is not None:
                    task_config["lead_time"] = int(leadtime_stop)
    
                # Dates use a space separator.
                start = cycles.get("start")
                stop = cycles.get("stop")
    
                if start is not None:
                    task_config["start_date"] = format_datetime(start)
    
                if stop is not None:
                    task_config["end_date"] = format_datetime(stop)
    
                # Preserve the order of variables in config_base.yaml.
                task_config["vars_of_interest"] = list(
                    variables.keys()
                )
    
            # =========================================================
            # plot_vx_grid and plot_vx_obs
            # =========================================================
            elif task_name in {"plot_vx_grid", "plot_vx_obs"}:
    
                # Dates retain the T separator.
                start = cycles.get("start")
                stop = cycles.get("stop")
    
                if start is not None:
                    task_config["start_date"] = (
                        start.isoformat(timespec="seconds")
                        if isinstance(start, datetime)
                        else str(start)
                    )
    
                if stop is not None:
                    task_config["end_date"] = (
                        stop.isoformat(timespec="seconds")
                        if isinstance(stop, datetime)
                        else str(stop)
                    )
    
                # Forecast frequency: '6:00:00' -> '6h'.
                leadtime_step = leadtimes.get("step")
    
                if leadtime_step is not None:
                    if (
                        isinstance(leadtime_step, str)
                        and ":" in leadtime_step
                    ):
                        hours = int(leadtime_step.split(":")[0])
                        task_config["freq"] = f"{hours}h"
                    else:
                        task_config["freq"] = leadtime_step
    
                # Convert lead times to integer hours.
                def time_to_hours(value):
                    if isinstance(value, str) and ":" in value:
                        hours, minutes, seconds = map(
                            int, value.split(":")
                        )
                        return hours + minutes / 60 + seconds / 3600
    
                    return int(value)
    
                task_config["leadtimes"] = {
                    "start": time_to_hours(leadtimes["start"]),
                    "end": time_to_hours(leadtimes["stop"]),
                    "step": time_to_hours(leadtimes["step"]),
                }
    
                # Build variable prefixes from variable definitions.
                prefixes = []
    
                for variable in variables.values():
                    name = variable["name"]
                    level_type = variable["level_type"]
                    levels = variable.get("levels", [])
    
                    if level_type == "surface":
                        prefixes.append(f"{name}_{level_type}")
                    else:
                        for level in levels:
                            prefixes.append(
                                f"{name}_{level_type}_{int(level):04d}"
                            )
    
                task_config["variable_prefixes"] = sorted(prefixes)
    
        logger.info(
            "Task '%s': generated %d top-level parameters.",
            task_name,
            len(task_config),
        )
    
        return task_config

    # -----------------------------------------------------------------
    # Write a task configuration
    # -----------------------------------------------------------------

    @staticmethod
    def write_task_config(
        task_name: str,
        task_config: dict[str, Any],
        output_dir: Path,
    ) -> Path:
        """Write one flattened task configuration to a YAML file."""
        output_file = output_dir / f"config_{task_name}.yaml"

        with output_file.open("w", encoding="utf-8") as stream:
            yaml.safe_dump(
                task_config,
                stream,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
                width=float("inf"),
            )

        logger.info("Generated: %s", output_file)

        return output_file

    # -----------------------------------------------------------------
    # Generate job cards / ecf scripts
    # -----------------------------------------------------------------

    def get_job_card_output_dir(self) -> tuple[Path, str]:
        """Return the job-card output directory and file suffix."""
    
        app_config = self.config.get("app", {})
        workflow_manager = app_config.get("workflow_manager")
    
        exp_case_name = app_config.get("exp_case_name")
        if not isinstance(exp_case_name, str) or not exp_case_name.strip():
            raise ValueError("'exp_case_name' must be a non-empty string.")
    
        exp_case_name = exp_case_name.strip()
        case_path = Path(exp_case_name)
    
        if (
            case_path.is_absolute()
            or len(case_path.parts) != 1
            or exp_case_name in {".", ".."}
        ):
            raise ValueError(f"Invalid exp_case_name: {exp_case_name!r}")
    
        exp_case_path = self.exp_cases_dir / exp_case_name
    
        if workflow_manager == "ecflow":
            ecf_suite_family_name = "ecf_scripts"
            job_card_dir = (
                exp_case_path / "ecf" / ecf_suite_family_name
            )
            job_card_suffix = ".ecf"
        else:
            job_card_dir = exp_case_path / "job_cards"
            job_card_suffix = ""
    
        job_card_dir.mkdir(parents=True, exist_ok=True)
    
        logger.info("Job-card output directory: %s", job_card_dir)
    
        return job_card_dir, job_card_suffix, exp_case_path
    
    
    def generate_job_cards(self) -> list[Path]:
        """Generate job cards for all tasks in config_base.yaml."""
    
        # Determine the destination directory and suffix.
        job_card_dir, job_card_suffix, exp_case_path = (
            self.get_job_card_output_dir()
        )
    
        # Load the job-card template.
        template_dir = self.script_dir / "templates"
    
        env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            undefined=StrictUndefined,
            keep_trailing_newline=True,
        )
    
        template = env.get_template("template.jobcard_task")
    
        # Load platform-specific configuration.
        platform_file = self.script_dir / "config_platform.yaml"
    
        with platform_file.open("r", encoding="utf-8") as stream:
            platform_config = yaml.safe_load(stream)

        # Get app configuration from config_base.yaml
        app_config = self.config.get("app", {})
        platform_name = app_config.get("platform")
        workflow_manager = app_config.get("workflow_manager")

        # Get NCO variables from config_base.yaml.
        nco_vars = self.config.get("nco_vars", {})
        envir = nco_vars.get("envir")        
        if not envir:
            raise ValueError("Missing required nco_vars.envir.")
        keepdata = nco_vars.get("KEEPDATA")
        if not keepdata:
            raise ValueError("Missing required nco_vars.KEEPDATA.")
        model_ver = nco_vars.get("model_ver")
        if not model_ver:
            raise ValueError("Missing required nco_vars.model_ver.")
        net = nco_vars.get("NET")
        if not net:
            raise ValueError("Missing required nco_vars.NET.")
        run = nco_vars.get("RUN")
        if not run:
            raise ValueError("Missing required nco_vars.RUN.")
        ops_path = nco_vars.get("OPS_PATH")
        if not ops_path:
            raise ValueError("Missing required nco_vars.OPS_PATH.")
        ops_path = Path(ops_path)

        platforms = platform_config.get("platforms", {}) 
        if platform_name not in platforms:
            raise ValueError(
                f"Unknown platform: {platform_name!r}"
            ) 
        platform = platforms[platform_name]
    
        # Determine the cycle date.
        cycles = self.config.get("common", {}).get("cycles", {})
        start_date = cycles.get("start")
    
        if start_date is None:
            raise ValueError("Missing common.cycles.start.")
    
        if isinstance(start_date, datetime):
            cycle_date = start_date
        else:
            cycle_date = datetime.fromisoformat(str(start_date))
    
        pdy_cdate = cycle_date.strftime("%Y%m%d")
        cyc_cdate = cycle_date.strftime("%H")

        # Create symlinks to NCO directories
        log_dir = ops_path / envir / "com" / "output" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        tmp_dir = ops_path / envir / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        com_dir = ops_path / envir / "com" / net / model_ver
        com_dir.mkdir(parents=True, exist_ok=True)

        exp_case_path.mkdir(parents=True, exist_ok=True)
        self.create_symlinks_dirs(
            exp_case_path,
            log_dir=log_dir,
            tmp_dir=tmp_dir,
            com_dir=com_dir,
        )

        # Generate job cards only for selected tasks.
        generated_files = []
        tasks = self.config["tasks"]
        task_list = self.validate_task_list()

        for task_name in task_list:
            task_definition = tasks[task_name]
   
            if not isinstance(task_definition, dict):
                raise ValueError(
                    f"Task '{task_name}' must be a mapping."
                )
    
            hpc = task_definition.get("hpc", {})
 
            nprocs = int(hpc.get("nprocs", 1))
            max_cores = int(platform["max_cores_per_node"])
            if nprocs < 1 or max_cores < 1:
                raise ValueError(
                    f"Invalid process configuration for '{task_name}'."
                )
    
            nnodes = (nprocs + max_cores - 1) // max_cores
            nprocs_per_node = (nprocs + nnodes -1) // nnodes

            external_data = bool(task_definition.get("external_data"))

            if workflow_manager == "ecflow":
                output_fn = (
                    f"{task_name}_%ECF_DATE%%CYC%_%ECF_TRYNO%.log"
                )
            else:
                output_fn = f"{task_name}.%j.log"
            output_name = str(log_dir / output_fn)

            context = {
                "account": app_config.get("account"),
                "cluster": platform.get("cluster"),
                "cluster_data": platform.get("cluster_data"),
                "constraint_data": platform.get("constraint_data"),
                "cyc_cdate": cyc_cdate,
                "envir": envir,
                "exp_case_path": str(exp_case_path),
                "external_data": external_data,
                "HOMEwxvx": str(self.repo_dir),
                "KEEPDATA": keepdata,
                "memory_flag": bool(hpc.get("memory_per_node")),
                "memory_per_node": hpc.get("memory_per_node"),
                "model_ver": model_ver,
                "native": platform.get("native"),
                "native_data": platform.get("native_data"),
                "NET": net,
                "nnodes": nnodes,
                "nprocs_per_node": nprocs_per_node,
                "OPS_PATH": ops_path,
                "output_name": output_name,
                "partition_queue": platform.get("partition_queue"),
                "partition_queue_data": platform.get("partition_queue_data"),
                "pdy_cdate": pdy_cdate,
                "platform": platform_name,
                "qos": platform.get("qos"),
                "RUN": run,
                "sched": platform.get("sched"),
                "task_name": task_name,
                "task_name_upper": task_name.upper(),
                "walltime": hpc.get("walltime", "00:30:00"),
                "workflow_manager": app_config.get("workflow_manager"),
            }
    
            # Render the template.
            rendered = template.render(**context)
    
            # Use the directory and suffix returned by the helper.
            output_file = (
                job_card_dir
                / f"jwxvx_{task_name}{job_card_suffix}"
            )
    
            with output_file.open("w", encoding="utf-8") as stream:
                stream.write(rendered)
    
            # Set executable permissions.
            output_file.chmod(0o755)
            logger.info("Generated job card: %s", output_file)
            generated_files.append(output_file)
    
        return generated_files

    # -----------------------------------------------------------------
    # Create symlinks to NCO directories
    # -----------------------------------------------------------------

    def create_symlinks_dirs(
        self,
        exp_case_path: Path,
        log_dir: Path,
        tmp_dir: Path,
        com_dir: Path,
    ) -> None:
        """Create symlinks to log, tmp, and com directories."""
        
        symlink_dirs = {
            "log_dir": log_dir,
            "tmp_dir": tmp_dir,
            "com_dir": com_dir,
        }
 
        for link_name, source_dir in symlink_dirs.items():
            link_path = exp_case_path / link_name

            # Create the source directory if it doesn't exist.
            source_dir.mkdir(parents=True, exist_ok=True)

            # Handle an existing symlink.
            if link_path.is_symlink():
                if link_path.resolve() == source_dir.resolve():
                    logger.debug("Symlink already exists: %s", link_path)
                    continue
    
                raise FileExistsError(
                    f"Symlink already exists and points elsewhere: {link_path}"
                )
    
            if link_path.exists():
                raise FileExistsError(
                    f"Cannot create symlink; destination already exists: {link_path}"
                )

            # Create the symlinks
            link_path.symlink_to(source_dir, target_is_directory=True)
    
            logger.info("Created symlink: %s -> %s", link_path, source_dir)

    # -----------------------------------------------------------------
    # Generate configurations and job cards for all tasks
    # -----------------------------------------------------------------

    def generate(self) -> list[Path]:
        """Generate reusable configuration groups and task configurations."""
    
        self.load_config()
        self.load_config_platform()

        # Resolve AUTO in some nco_vars parameters
        if self.config["nco_vars"].get("OPS_PATH") == "AUTO":
            self.config["nco_vars"]["OPS_PATH"] = str(self.default_ops_path)

        if self.config["nco_vars"].get("RUN") == "AUTO":
            self.config["nco_vars"]["RUN"] = self.config["app"]["exp_case_name"]

        output_dir = self.get_output_dir()
        generated_files: list[Path] = []
    
        # Generate reusable configuration files, such as config_common.yaml.
        for group_name, group_definition in self.config.items():
    
            if not group_name.startswith("config_"):
                continue
    
            if not isinstance(group_definition, list):
                raise ValueError(
                    f"Reusable group '{group_name}' must be a list "
                    "of parameter group names."
                )
    
            config_name = group_name.removeprefix("config_")
    
            group_config = self.build_task_config(
                task_name=config_name,
                group_names=[group_name],
            )
    
            output_file = self.write_task_config(
                task_name=config_name,
                task_config=group_config,
                output_dir=output_dir,
            )
    
            generated_files.append(output_file)
    
        # Generate task-specific configuration files.
        tasks = self.config["tasks"]
        task_list = self.validate_task_list()

        for task_name in task_list:
            task_definition = tasks[task_name]

            if not isinstance(task_definition, dict):
                raise ValueError(
                    f"Task '{task_name}' must be a dictionary."
                )

            group_names = task_definition.get("groups", [])
            hpc_params = task_definition.get("hpc", {})

            if not isinstance(group_names, list):
                raise ValueError(
                    f"Task '{task_name}': 'groups' must be a list."
                )

            if not isinstance(hpc_params, dict):
                raise ValueError(
                    f"Task '{task_name}': 'hpc' must be a dictionary."
                )

            task_config = self.build_task_config(
                task_name=task_name,
                group_names=group_names,
                hpc_params=hpc_params,
            )

            output_file = self.write_task_config(
                task_name=task_name,
                task_config=task_config,
                output_dir=output_dir,
            )

            generated_files.append(output_file)
    
        logger.info(
            "Successfully generated %d configuration file(s).",
            len(generated_files),
        )

        # Generate job cards (ecf scripts)
        job_cards = self.generate_job_cards()

        return generated_files + job_cards

# ---------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------

def main() -> int:
    """Parse command-line arguments and generate configurations."""
    parser = argparse.ArgumentParser(
        description=(
            "Generate flattened WXVX task configuration files "
            "from config_base.yaml."
        )
    )

    parser.add_argument(
        "--config",
        default="config_base.yaml",
        help=(
            "Input YAML configuration file. Relative paths are "
            "resolved relative to the parm directory."
        ),
    )

    args = parser.parse_args()

    try:
        generator = ConfigGenerator(config_file=args.config)
        generator.generate()

    except (OSError, ValueError, yaml.YAMLError) as exc:
        logger.error("%s", exc)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
