from __future__ import annotations

from enum import StrEnum


class JobState(StrEnum):
    QUEUED = "queued"
    PARSING = "parsing"
    RETRIEVING = "retrieving"
    GENERATING = "generating"
    PACKAGING = "packaging"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class InvalidJobTransitionError(ValueError):
    """A requested job state transition is not permitted."""


_ALLOWED_TRANSITIONS = {
    JobState.QUEUED: {JobState.PARSING, JobState.CANCELLED},
    JobState.PARSING: {
        JobState.RETRIEVING,
        JobState.FAILED,
        JobState.CANCELLED,
    },
    JobState.RETRIEVING: {
        JobState.GENERATING,
        JobState.FAILED,
        JobState.CANCELLED,
    },
    JobState.GENERATING: {
        JobState.PACKAGING,
        JobState.FAILED,
        JobState.CANCELLED,
    },
    JobState.PACKAGING: {
        JobState.COMPLETED,
        JobState.FAILED,
        JobState.CANCELLED,
    },
    JobState.COMPLETED: set(),
    JobState.FAILED: set(),
    JobState.CANCELLED: set(),
}

_RETRYABLE_STATES = {
    JobState.PARSING,
    JobState.RETRIEVING,
    JobState.GENERATING,
    JobState.PACKAGING,
}

_PROGRESS = {
    JobState.QUEUED: 0,
    JobState.PARSING: 10,
    JobState.RETRIEVING: 35,
    JobState.GENERATING: 60,
    JobState.PACKAGING: 90,
    JobState.COMPLETED: 100,
    JobState.FAILED: 100,
    JobState.CANCELLED: 100,
}


def require_transition(
    current: JobState,
    target: JobState,
    *,
    allow_retry: bool = False,
) -> None:
    if target in _ALLOWED_TRANSITIONS[current]:
        return
    if (
        allow_retry
        and current in _RETRYABLE_STATES
        and target is JobState.QUEUED
    ):
        return
    raise InvalidJobTransitionError(
        f"transition from {current.value} to {target.value} is not allowed"
    )


def public_status(state: JobState) -> str:
    if state is JobState.QUEUED:
        return "queued"
    if state in {
        JobState.PARSING,
        JobState.RETRIEVING,
        JobState.GENERATING,
        JobState.PACKAGING,
    }:
        return "running"
    if state is JobState.COMPLETED:
        return "completed"
    return "failed"


def progress_for(state: JobState) -> int:
    return _PROGRESS[state]


def is_terminal(state: JobState) -> bool:
    return state in {
        JobState.COMPLETED,
        JobState.FAILED,
        JobState.CANCELLED,
    }
