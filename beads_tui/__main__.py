"""Entry point for python -m beads_tui."""

from __future__ import annotations

import argparse

from beads_tui.app import BeadsTuiApp, AVAILABLE_COLUMNS, DEFAULT_COLUMNS


def main() -> None:
    parser = argparse.ArgumentParser(description="Interactive TUI for beads")
    parser.add_argument(
        "--columns",
        type=str,
        default=None,
        help=(
            "Comma-separated list of columns: "
            + ",".join(AVAILABLE_COLUMNS.keys())
        ),
    )
    parser.add_argument(
        "--all",
        action="store_true",
        default=False,
        help="Show all issues including closed",
    )
    parser.add_argument(
        "--bd-path",
        type=str,
        default=None,
        help="Path to bd binary",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Path to bd database",
    )

    args = parser.parse_args()

    columns: list[str] | None = None
    if args.columns:
        raw = [c.strip() for c in args.columns.split(",") if c.strip()]
        valid = [c for c in raw if c in AVAILABLE_COLUMNS]
        if valid:
            columns = valid

    app = BeadsTuiApp(
        bd_path=args.bd_path,
        db_path=args.db_path,
        columns=columns,
        show_all=args.all,
    )
    app.run()


if __name__ == "__main__":
    main()
