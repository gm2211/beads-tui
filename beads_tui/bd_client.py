"""Async subprocess wrapper around the bd CLI."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from pathlib import Path
from typing import Any, Optional

from .models import Comment, DbStatus, Issue


class BdError(Exception):
    """Base exception for bd client errors."""


class BdNotFoundError(BdError):
    """Raised when the bd binary cannot be found."""


class BdCommandError(BdError):
    """Raised when a bd command fails."""

    def __init__(self, message: str, returncode: int = 1, stderr: str = ""):
        super().__init__(message)
        self.returncode = returncode
        self.stderr = stderr


def _discover_bd_path() -> str:
    """Find the bd binary, checking PATH then common locations."""
    found = shutil.which("bd")
    if found:
        return found
    for candidate in [
        Path.home() / ".local" / "bin" / "bd",
        Path("/usr/local/bin/bd"),
    ]:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    raise BdNotFoundError(
        "bd binary not found. Install it or pass bd_path= to BdClient."
    )


class BdClient:
    """Async client that wraps the bd CLI with JSON parsing."""

    def __init__(
        self,
        bd_path: str | None = None,
        db_path: str | None = None,
    ):
        self._bd_path = bd_path or _discover_bd_path()
        self._db_path = db_path

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _base_args(self) -> list[str]:
        args = [self._bd_path]
        if self._db_path:
            args += ["--db", self._db_path]
        return args

    async def _run_bd(
        self,
        *args: str,
        parse_json: bool = True,
    ) -> Any:
        """Run a bd command asynchronously and return parsed output.

        When *parse_json* is True the ``--json`` flag is appended and the
        stdout is decoded as JSON.  Otherwise the raw stdout string is
        returned.
        """
        cmd = self._base_args()
        cmd.extend(args)
        if parse_json and "--json" not in cmd:
            cmd.append("--json")

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await proc.communicate()
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")

        if proc.returncode != 0:
            raise BdCommandError(
                f"bd command failed (exit {proc.returncode}): {stderr.strip() or stdout.strip()}",
                returncode=proc.returncode,
                stderr=stderr,
            )

        if not parse_json:
            return stdout

        if not stdout.strip():
            return None

        try:
            return json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise BdCommandError(
                f"Failed to parse bd JSON output: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Issue queries
    # ------------------------------------------------------------------

    async def list_issues(
        self,
        status: str | None = None,
        priority: str | int | None = None,
        type_: str | None = None,
        assignee: str | None = None,
        limit: int = 50,
        sort: str | None = None,
        all_: bool = False,
    ) -> list[Issue]:
        args: list[str] = ["list"]
        if all_:
            args.append("--all")
        if status:
            args += ["--status", status]
        if priority is not None:
            args += ["--priority", str(priority)]
        if type_:
            args += ["--type", type_]
        if assignee:
            args += ["--assignee", assignee]
        if limit:
            args += ["--limit", str(limit)]
        if sort:
            args += ["--sort", sort]

        data = await self._run_bd(*args)
        if not data:
            return []
        return [Issue.from_dict(item) for item in data]

    async def show_issue(self, issue_id: str) -> Issue:
        data = await self._run_bd("show", issue_id)
        if not data:
            raise BdCommandError(f"Issue not found: {issue_id}")
        if isinstance(data, list):
            if not data:
                raise BdCommandError(f"Issue not found: {issue_id}")
            return Issue.from_dict(data[0])
        return Issue.from_dict(data)

    async def search_issues(
        self,
        query: str,
        status: str | None = None,
        priority: str | int | None = None,
        limit: int = 50,
    ) -> list[Issue]:
        args: list[str] = ["search", query]
        if status:
            args += ["--status", status]
        if priority is not None:
            args += ["--priority", str(priority)]
        if limit:
            args += ["--limit", str(limit)]

        data = await self._run_bd(*args)
        if not data:
            return []
        return [Issue.from_dict(item) for item in data]

    # ------------------------------------------------------------------
    # Issue mutations
    # ------------------------------------------------------------------

    async def create_issue(
        self,
        title: str,
        description: str | None = None,
        priority: str | int | None = None,
        type_: str | None = None,
        assignee: str | None = None,
        labels: list[str] | None = None,
    ) -> str:
        """Create a new issue and return its ID."""
        args: list[str] = ["create", "--title", title, "--silent"]
        if description:
            args += ["--description", description]
        if priority is not None:
            args += ["--priority", str(priority)]
        if type_:
            args += ["--type", type_]
        if assignee:
            args += ["--assignee", assignee]
        if labels:
            args += ["--labels", ",".join(labels)]

        output = await self._run_bd(*args, parse_json=False)
        return output.strip()

    async def update_issue(self, issue_id: str, **kwargs: Any) -> None:
        """Update fields on an issue.

        Supported kwargs: title, status, priority, assignee, description,
        notes, labels (set-labels), type_.
        """
        args: list[str] = ["update", issue_id]

        field_map = {
            "title": "--title",
            "status": "--status",
            "priority": "--priority",
            "assignee": "--assignee",
            "description": "--description",
            "notes": "--notes",
            "type_": "--type",
            "due": "--due",
            "defer": "--defer",
            "estimate": "--estimate",
            "acceptance": "--acceptance",
            "design": "--design",
            "external_ref": "--external-ref",
        }

        for key, flag in field_map.items():
            if key in kwargs and kwargs[key] is not None:
                args += [flag, str(kwargs[key])]

        if "labels" in kwargs and kwargs["labels"] is not None:
            args += ["--set-labels", ",".join(kwargs["labels"])]

        await self._run_bd(*args, parse_json=False)

    async def close_issue(self, issue_id: str, reason: str | None = None) -> None:
        args: list[str] = ["close", issue_id]
        if reason:
            args += ["--reason", reason]
        await self._run_bd(*args, parse_json=False)

    async def reopen_issue(self, issue_id: str) -> None:
        await self._run_bd("reopen", issue_id, parse_json=False)

    # ------------------------------------------------------------------
    # Comments
    # ------------------------------------------------------------------

    async def list_comments(self, issue_id: str) -> list[Comment]:
        data = await self._run_bd("comments", issue_id)
        if not data:
            return []
        return [Comment.from_dict(item) for item in data]

    async def add_comment(self, issue_id: str, text: str) -> None:
        await self._run_bd("comments", "add", issue_id, text, parse_json=False)

    # ------------------------------------------------------------------
    # Labels
    # ------------------------------------------------------------------

    async def add_label(self, issue_id: str, label: str) -> None:
        await self._run_bd("label", "add", issue_id, label, parse_json=False)

    async def remove_label(self, issue_id: str, label: str) -> None:
        await self._run_bd("label", "remove", issue_id, label, parse_json=False)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    async def get_status(self) -> DbStatus:
        data = await self._run_bd("status")
        if not data:
            return DbStatus()
        return DbStatus.from_dict(data)
