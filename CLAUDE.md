# beads-tui

Python Textual TUI for the beads (bd) issue tracker.

## Project Conventions

### Keybindings
- Every new keybinding added to `BINDINGS` in any screen or `app.py` **must** also be added to `beads_tui/screens/help_screen.py` in the `HELP_TEXT` string under the appropriate section.
- Sections in help: Global, Issue List, Quick Actions (List), Columns & Sorting, Detail View.

### Rich Markup in Widgets
- `Static` widgets render Rich markup. Never use bare square brackets `[text]` in display strings — Rich interprets them as tags and silently swallows the content. Use `\[` to escape or avoid brackets entirely.

### Auto-Refresh
- Always pair `pause_refresh()` with `resume_refresh()` in a `try/finally` block when opening modals or screens that should suppress background refresh.
- The fallback poll interval is 10 seconds. The file watcher checks every 1 second.

### Worktrees
- All worktrees share the same `.beads/` Dolt database from the main repo root.
- Worktree identity in the status bar uses the git branch name (`git rev-parse --abbrev-ref HEAD`).
