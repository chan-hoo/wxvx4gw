#!/usr/bin/env python3
"""
Generate task-specific WXVX configuration files.

Read config_base.yaml, combine the parameter groups specified for
each task, and write flattened config_[task].yaml files.

Expected input structure:

    parm/
    ├── config_base.yaml
    └── setup.py

Expected output structure:

    parm/exp_cases/<exp_case_name>/configs/
        ├── config_common.yaml
        ├── config_<task1>.yaml
        └── config_<task2>.yaml

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
from datetime import datetime

import yaml


# ---------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
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
    # Parameter-specific default values when AUTO
    # -----------------------------------------------------------------
    
    AUTO_RULES = {
        "nco_vars.OPS_PATH": "{repo_dir}/PTMP",
        "vx_common.meta.post_files": "{COMINOUT}/vx/post_files",
        "vx_common.forecast.path":(
            '{{ meta.post_files }}/nested-global.{{ yyyymmdd[:4] }}-{{ yyyymmdd[4:6] }}-'
            '{{ yyyymmdd[6:8] }}T{{ hh }}.{{ "%02d" % meta.max_leadtime }}h.nc'
            ),
        "vx_grid2grid.meta.workdir": "{COMINOUT}/vx/grid2grid",
        "vx_grid2grid.meta.grids": "{COMINOUT}/vx/grid2grid/grids",
        "vx_grid2grid.truth.url":(
            'https://noaa-gfs-bdp-pds.s3.amazonaws.com/'
            'gfs.{{ yyyymmdd }}/{{ hh }}/atmos/'
            'gfs.t{{ hh }}z.pgrb2.0p25.f{{ "%03d" % fh }}'
            ),
        "vx_grid2grid.paths.grids.forecast": "{COMINOUT}/vx/grid2grid/grids/forecast",
        "vx_grid2grid.paths.grids.truth": "{COMINOUT}/vx/grid2grid/grids/truth",
        "vx_grid2grid.paths.run": "{COMINOUT}/vx/grid2grid/run",
        "vx_grid2obs.meta.workdir": "{COMINOUT}/vx/grid2obs",
        "vx_grid2obs.meta.grids": "{COMINOUT}/vx/grid2obs/grids",
        "vx_grid2obs.truth.url":(
            'https://noaa-reanalyses-pds.s3.amazonaws.com/observations/reanalysis/conv/prepbufr/'
            '{{ yyyymmdd[:4] }}/{{ yyyymmdd[4:6] }}/prepbufr/gdas.{{ yyyymmdd }}.t{{ hh }}z.prepbufr.nr'
            ),
        "vx_grid2obs.paths.grids.forecast": "{COMINOUT}/vx/grid2obs/forecast",
        "vx_grid2obs.paths.obs": "{COMINOUT}/vx/grid2obs/obs",
        "vx_grid2obs.paths.run": "{COMINOUT}/vx/grid2obs/run",
        "prewxvx.forecast_path": "{COMINOUT}/inference",
        "prewxvx.output_path": "{COMINOUT}/vx/post_files",
        "prewxvx.anemoi_reference_dataset_kwargs.cutout[0].dataset": "{COMINOUT}/data/hrrr.zarr",
        "prewxvx.anemoi_reference_dataset_kwargs.cutout[1].dataset": "{COMINOUT}/data/gfs.zarr",
        "prewxvx.forecast_regrid_kwargs.target_grid_path": "{COMINOUT}/data/global_one_degree.nc",
        "plot_vx_grid.work_path": "{COMINOUT}/vx/grid2grid",
        "plot_vx_obs.work_path": "{COMINOUT}/vx/grid2obs",
    }

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
    
        # Default OPS directory under the repository root.
        self.default_ops_path = self.repo_dir / "PTMP"
    
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

        logger.info(
            "Found %d task(s).",
            len(self.config["tasks"]),
        )

        return self.config

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
    # Resolve configuration parms when set to AUTO
    # -----------------------------------------------------------------

    def get_auto_context(self) -> dict[str, str]:
        """Collect configuration values and construct common paths."""
    
        context = {
            "repo_dir": str(self.repo_dir),
        }
    
        # Collect parameters from app and nco_vars.
        for group_name in ("app", "nco_vars"):
            group = self.config.get(group_name, {})
    
            if not isinstance(group, dict):
                raise ValueError(
                    f"Configuration group '{group_name}' must be a mapping."
                )
    
            for key, value in group.items():
                if value is not None and not isinstance(value, (dict, list)):
                    context[key] = str(value)
    
        # Resolve OPS_PATH=AUTO before constructing COMINOUT.
        ops_path = context.get("OPS_PATH")
    
        if ops_path is None or ops_path.strip().upper() == "AUTO":
            ops_path = str(self.default_ops_path)
    
        context["OPS_PATH"] = ops_path
    
        # Construct the COMINOUT directory.
        required = ("envir", "NET", "model_ver", "RUN")
        missing = [key for key in required if not context.get(key)]
    
        if missing:
            raise ValueError(
                "Cannot construct cominout. Missing parameters: "
                + ", ".join(missing)
            )
    
        COMINOUT = (
            Path(ops_path)
            / context["envir"]
            / context["NET"]
            / context["model_ver"]
            / context["RUN"]
        )
    
        context["COMINOUT"] = str(COMINOUT)
    
        logger.info("OPS_PATH: %s", ops_path)
        logger.info("COMINOUT: %s", COMINOUT)
    
        return context


    def resolve_auto_value(
        self,
        parameter_name: str,
        context: dict[str, str],
        full_path: str,
    ) -> Any:
        """Resolve AUTO values using their full configuration paths."""
    
        template = self.AUTO_RULES.get(full_path)
    
        if template is None:
            raise ValueError(
                f"No AUTO resolution rule defined for '{full_path}'."
            )
    
        # Preserve Jinja2 expressions exactly.
        return template


    def resolve_auto_parameters(self) -> None:
        """Resolve AUTO values in nested dictionaries and lists."""
    
        context = self.get_auto_context()
    
        def resolve_value(value: Any, prefix: str = "") -> Any:
            """Recursively resolve AUTO values."""
    
            if isinstance(value, dict):
                for key, item in value.items():
                    full_path = f"{prefix}.{key}" if prefix else key
    
                    value[key] = resolve_value(
                        item,
                        prefix=full_path,
                    )
    
                return value
    
            if isinstance(value, list):
                for index, item in enumerate(value):
                    value[index] = resolve_value(
                        item,
                        prefix=f"{prefix}[{index}]",
                    )
    
                return value

            if isinstance(value, str) and value.strip().upper() == "AUTO":
                template = self.AUTO_RULES.get(prefix)
            
                if template is None:
                    raise ValueError(
                        f"No AUTO resolution rule defined for '{prefix}'."
                    )
            
                # Preserve Jinja2 expressions; format ordinary path templates.
                if "{{" in template and "}}" in template:
                    resolved = template
                else:
                    try:
                        resolved = template.format_map(context)
                    except KeyError as exc:
                        raise ValueError(
                            f"Cannot resolve '{prefix}': missing context "
                            f"parameter {exc.args[0]!r}."
                        ) from exc
            
                return resolved

            return value
    
        for group_name, group_config in self.config.items():
            if group_name == "tasks":
                continue
    
            if (
                group_name.startswith("config_")
                and isinstance(group_config, list)
            ):
                continue
    
            if isinstance(group_config, (dict, list)):
                self.config[group_name] = resolve_value(
                    group_config,
                    prefix=group_name,
                )

    # -----------------------------------------------------------------
    # Recursively merge group parameters
    # -----------------------------------------------------------------

    def deep_merge(
        self,
        target: dict,
        source: dict,
    ) -> dict:
        """
        Recursively merge source into target.
    
        - Preserve parameters that exist only in either dictionary.
        - Recursively merge nested dictionaries.
        - If the same parameter exists in both dictionaries,
          the value from source takes precedence.
        """
        for key, value in source.items():
            if (
                key in target
                and isinstance(target[key], dict)
                and isinstance(value, dict)
            ):
                self.deep_merge(target[key], value)
            else:
                target[key] = value
    
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
    ) -> dict[str, Any]:
        """
        Build a flattened configuration for a task.
    
        Special handling:
          - common: add platform-specific parameters.
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
        # Add platform-specific parameters to config_common.yaml.
        # -------------------------------------------------------------
        if task_name == "common":
            task_config.update(self.platform_params)
    
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
    # Generate configurations for all tasks
    # -----------------------------------------------------------------

    def generate(self) -> list[Path]:
        """Generate reusable configuration groups and task configurations."""
    
        self.load_config()
        self.load_config_platform()

        # Resolve all AUTO parameters before generating YAML files.
        self.resolve_auto_parameters()
    
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
    
        for task_name, group_names in tasks.items():
    
            task_config = self.build_task_config(
                task_name=task_name,
                group_names=group_names,
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
    
        return generated_files

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
