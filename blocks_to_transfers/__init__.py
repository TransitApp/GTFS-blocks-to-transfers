# Exposing the core API to allow using via python-code (not just via CLI)

from . import processing, runtime_config

def process_with_config(in_dir,
            out_dir,
            config_override,
            use_simplify_linear=False,
            remove_existing_files=False,
            sorted_io=False,
            ):
    runtime_config.apply(config_override)
    processing.process(in_dir, out_dir, use_simplify_linear, remove_existing_files, sorted_io)

__all__ = ["process_with_config"]
