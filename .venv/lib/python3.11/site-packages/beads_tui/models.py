"""Data models for bd CLI JSON output."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Dependency:
    """A dependency relationship between issues."""

    issue_id: str = ""
    depends_on_id: str = ""
    type: str = ""
    created_at: str = ""
    created_by: str = ""
    # Fields present when shown via `bd show --json` (expanded form)
    id: str = ""
    title: str = ""
    description: str = ""
    status: str = ""
    priority: int = -1
    issue_type: str = ""
    owner: str = ""
    dependency_type: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> Dependency:
        return cls(
            issue_id=data.get("issue_id", ""),
            depends_on_id=data.get("depends_on_id", ""),
            type=data.get("type", ""),
            created_at=data.get("created_at", ""),
            created_by=data.get("created_by", ""),
            id=data.get("id", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            status=data.get("status", ""),
            priority=data.get("priority", -1),
            issue_type=data.get("issue_type", ""),
            owner=data.get("owner", ""),
            dependency_type=data.get("dependency_type", ""),
        )


@dataclass
class Issue:
    """An issue from bd."""

    id: str = ""
    title: str = ""
    description: str = ""
    status: str = ""
    priority: int = 2
    issue_type: str = ""
    owner: str = ""
    created_at: str = ""
    created_by: str = ""
    updated_at: str = ""
    # Counts (from list view)
    dependency_count: int = 0
    dependent_count: int = 0
    comment_count: int = 0
    # Expanded relations (from show view)
    dependencies: list[Dependency] = field(default_factory=list)
    dependents: list[Dependency] = field(default_factory=list)
    parent: Optional[str] = None
    # Optional fields that may appear on some issues
    notes: str = ""
    labels: list[str] = field(default_factory=list)
    assignee: str = ""
    due_at: Optional[str] = None
    defer_until: Optional[str] = None
    closed_at: Optional[str] = None
    external_ref: str = ""
    estimate: Optional[int] = None
    acceptance: str = ""
    design: str = ""
    mol_type: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> Issue:
        deps = [Dependency.from_dict(d) for d in data.get("dependencies", []) or []]
        depnts = [Dependency.from_dict(d) for d in data.get("dependents", []) or []]
        labels = data.get("labels") or []
        if isinstance(labels, str):
            labels = [l.strip() for l in labels.split(",") if l.strip()]

        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            status=data.get("status", ""),
            priority=data.get("priority", 2),
            issue_type=data.get("issue_type", ""),
            owner=data.get("owner", ""),
            created_at=data.get("created_at", ""),
            created_by=data.get("created_by", ""),
            updated_at=data.get("updated_at", ""),
            dependency_count=data.get("dependency_count", 0),
            dependent_count=data.get("dependent_count", 0),
            comment_count=data.get("comment_count", 0),
            dependencies=deps,
            dependents=depnts,
            parent=data.get("parent"),
            notes=data.get("notes", ""),
            labels=labels,
            assignee=data.get("assignee", ""),
            due_at=data.get("due_at"),
            defer_until=data.get("defer_until"),
            closed_at=data.get("closed_at"),
            external_ref=data.get("external_ref", ""),
            estimate=data.get("estimate"),
            acceptance=data.get("acceptance", ""),
            design=data.get("design", ""),
            mol_type=data.get("mol_type", ""),
        )


@dataclass
class Comment:
    """A comment on an issue."""

    id: int = 0
    issue_id: str = ""
    author: str = ""
    text: str = ""
    created_at: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> Comment:
        return cls(
            id=data.get("id", 0),
            issue_id=data.get("issue_id", ""),
            author=data.get("author", ""),
            text=data.get("text", ""),
            created_at=data.get("created_at", ""),
        )


@dataclass
class StatusSummary:
    """Summary statistics from bd status --json."""

    total_issues: int = 0
    open_issues: int = 0
    in_progress_issues: int = 0
    closed_issues: int = 0
    blocked_issues: int = 0
    deferred_issues: int = 0
    ready_issues: int = 0
    tombstone_issues: int = 0
    pinned_issues: int = 0
    epics_eligible_for_closure: int = 0
    average_lead_time_hours: float = 0.0

    @classmethod
    def from_dict(cls, data: dict) -> StatusSummary:
        return cls(
            total_issues=data.get("total_issues", 0),
            open_issues=data.get("open_issues", 0),
            in_progress_issues=data.get("in_progress_issues", 0),
            closed_issues=data.get("closed_issues", 0),
            blocked_issues=data.get("blocked_issues", 0),
            deferred_issues=data.get("deferred_issues", 0),
            ready_issues=data.get("ready_issues", 0),
            tombstone_issues=data.get("tombstone_issues", 0),
            pinned_issues=data.get("pinned_issues", 0),
            epics_eligible_for_closure=data.get("epics_eligible_for_closure", 0),
            average_lead_time_hours=data.get("average_lead_time_hours", 0.0),
        )


@dataclass
class RecentActivity:
    """Recent activity statistics from bd status --json."""

    hours_tracked: int = 0
    commit_count: int = 0
    issues_created: int = 0
    issues_closed: int = 0
    issues_updated: int = 0
    issues_reopened: int = 0
    total_changes: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> RecentActivity:
        return cls(
            hours_tracked=data.get("hours_tracked", 0),
            commit_count=data.get("commit_count", 0),
            issues_created=data.get("issues_created", 0),
            issues_closed=data.get("issues_closed", 0),
            issues_updated=data.get("issues_updated", 0),
            issues_reopened=data.get("issues_reopened", 0),
            total_changes=data.get("total_changes", 0),
        )


@dataclass
class DbStatus:
    """Database status from bd status --json."""

    summary: StatusSummary = field(default_factory=StatusSummary)
    recent_activity: RecentActivity = field(default_factory=RecentActivity)

    @classmethod
    def from_dict(cls, data: dict) -> DbStatus:
        return cls(
            summary=StatusSummary.from_dict(data.get("summary", {})),
            recent_activity=RecentActivity.from_dict(data.get("recent_activity", {})),
        )
