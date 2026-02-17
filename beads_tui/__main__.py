"""Entry point for python -m beads_tui."""

from beads_tui.app import BeadsTuiApp


def main() -> None:
    app = BeadsTuiApp()
    app.run()


if __name__ == "__main__":
    main()
