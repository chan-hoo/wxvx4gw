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

    ../exp_cases/<exp_case_name>/config/
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
# Configuration generator
# ---------------------------------------------------------------------

class ConfigGenerator:
    """Generate flattened YAML configuration files for WXVX tasks."""

    # -----------------------------------------------------------------
    # Parameter-specific default values when AUTO
    # -----------------------------------------------------------------

    AUTO_RULES = {
        "nco_vars.OPS_PATH": "{repo_dir}/PTMP",
        "vx_common.meta.post_files":(
            "test1"
            ),
        "vx_common.forecast.path":(
            '{{ meta.post_files }}/nested-global.'
            '{{ yyyymmdd[:4] }}-{{ yyyymmdd[4:6] }}-'
            '{{ yyyymmdd[6:8] }}T{{ hh }}.'
            '{{ "%02d" % meta.max_leadtime }}h.nc'
            ),
        "vx_grid2grid.meta.workdir":(
            "test2"
            ),
        "vx_grid2grid.meta.grids":(
            "test3"
            ),
        "vx_grid2grid.truth.url":(
            'https://noaa-gfs-bdp-pds.s3.amazonaws.com/'
            'gfs.{{ yyyymmdd }}/{{ hh }}/atmos/'
            'gfs.t{{ hh }}z.pgrb2.0p25.f{{ "%03d" % fh }}'
            ),
        "vx_grid2grid.paths.grids.forecast":(
            "test4"
            ),
        "vx_grid2grid.paths.grids.truth":(
            "test5"
            ),
        "vx_grid2grid.paths.run":(
            "test6"
            ),
        "vx_grid2obs.meta.workdir":(
            "test7"
            ),
        "vx_grid2obs.meta.grids":(
            "test8"
            ),
        "vx_grid2obs.truth.url":(
            'https://noaa-reanalyses-pds.s3.amazonaws.com/'
            'observations/reanalysis/conv/prepbufr/'
            '{{ yyyymmdd[:4] }}/{{ yyyymmdd[4:6] }}/prepbufr/'
            'gdas.{{ yyyymmdd }}.t{{ hh }}z.prepbufr.nr'
            ),
        "vx_grid2obs.paths.grids.forecast":(
            "test9"
            ),
        "vx_grid2obs.paths.obs":(
            "test10"
            ),
        "vx_grid2obs.paths.run":(
            "test11"
            ),
        "prewxvx.anemoi_reference_dataset_kwargs.cutout[0].dataset":(
            "test12"
            ),
        "prewxvx.anemoi_reference_dataset_kwargs.cutout[1].dataset":(
            "test13"
            ),
        "prewxvx.forecast_regrid_kwargs.target_grid_path":(
            "test14"
            ),
        "plot.work_path":(
            "test15"
            ),
    }

    # -----------------------------------------------------------------
    # Initialize
    # -----------------------------------------------------------------

    def __init__(
        self,
        config_file: str | Path = "config_base.yaml",
    ) -> None:
        """
        Initialize the configuration generator.

        Parameters
        ----------
        config_file : str or pathlib.Path
            Path to config_base.yaml. Relative paths are resolved
            relative to the directory containing this script.
        """
        self.script_dir = Path(__file__).resolve().parent

        config_path = Path(config_file).expanduser()

        if not config_path.is_absolute():
            config_path = self.script_dir / config_path

        self.config_file = config_path.resolve()

        # The wxvx4gw repository root is the parent of parm/.
        self.repo_dir = self.script_dir.parent

        # Experiment cases directory under the repository root.
        self.exp_cases_dir = self.repo_dir / "exp_cases"
        
        # Default OPS directory under the repository root.
        self.default_ops_path = self.repo_dir / "PTMP"

        self.config: dict[str, Any] = {}

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
    # Resolve configuration parms when set to AUTO
    # -----------------------------------------------------------------

    def get_auto_context(self) -> dict[str, str]:
        """Collect values used to resolve AUTO parameters."""
    
        context = {
            "repo_dir": str(self.repo_dir),
        }
    
        for group_name in ("app", "nco_vars"):
            group = self.config.get(group_name, {})
    
            if not isinstance(group, dict):
                raise ValueError(
                    f"Configuration group '{group_name}' must be a mapping."
                )
    
            for key, value in group.items():
                if value is not None and not isinstance(value, (dict, list)):
                    context[key] = str(value)
    
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
            
                resolved = self.resolve_auto_value(
                    parameter_name=prefix.rsplit(".", 1)[-1],
                    context=context,
                    full_path=prefix,
                )
            
                logger.info("Resolved %s=AUTO", prefix)
            
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
    
        A configuration group can be:
          1. A dictionary containing parameter values.
          2. A list of other configuration group names.
    
        List-based groups are expanded recursively.
    
        Nested dictionaries are merged recursively, and values from
        later groups take precedence when parameter names conflict.
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
                    # Expand reusable groups such as config_common.
                    if group_name in visited:
                        raise ValueError(
                            f"Circular configuration reference detected "
                            f"for group '{group_name}' in task '{task_name}'."
                        )
    
                    merge_groups(
                        group_config,
                        target,
                        visited | {group_name},
                    )
    
                elif isinstance(group_config, dict):
                    # Merge actual parameter values.
                    self.deep_merge(target, group_config)
    
                else:
                    raise ValueError(
                        f"Configuration group '{group_name}' must be "
                        "a dictionary or a list of group names."
                    )
    
        merge_groups(group_names, task_config)
    
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
