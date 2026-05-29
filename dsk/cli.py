"""Command-line interface for DSK simulations."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dsk.io.config import load_simulation


def main() -> int:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="dsk",
        description="DSK Python Port — Economic Agent-Based Model",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- run subcommand ---
    run_parser = subparsers.add_parser(
        "run",
        help="Run a single simulation from a YAML config",
    )
    run_parser.add_argument(
        "--simulation",
        type=str,
        required=True,
        help="Path to the simulation YAML file",
    )
    run_parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output directory for parquet files",
    )

    args = parser.parse_args()

    if args.command == "run":
        return run_command(args.simulation, args.output)
    elif args.command is None:
        parser.print_help()
        return 0
    else:
        parser.print_help()
        return 1


def run_command(simulation_path: str, output_dir: str) -> int:
    """Execute the 'run' subcommand."""
    try:
        # Load the simulation from YAML
        sim = load_simulation(simulation_path)

        # Run for the configured number of steps
        n_steps = sim.global_params.total_steps
        print(f"Running {n_steps} steps...")
        sim.run(n_steps)

        # Flush outputs
        output_dir_path = Path(output_dir)
        print(f"Flushing outputs to {output_dir}...")
        written = sim.flush(output_dir_path)

        if written:
            print(f"✓ Wrote {len(written)} parquet file(s)")
            for table_name, path in written.items():
                print(f"  - {table_name}.parquet ({path.stat().st_size} bytes)")
        else:
            print("⚠ No outputs were written")
            return 1

        return 0

    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
