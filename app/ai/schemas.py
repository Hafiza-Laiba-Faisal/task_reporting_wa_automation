from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class TaskExtraction(BaseModel):
    task: str = Field(..., min_length=3)
    assignee: str | None = None
    deadline: str | None = None
    priority: str | None = None
    status: str | None = None
    source_message: str = Field(..., min_length=3)
    sender: str = Field(..., min_length=1)
    message_timestamp: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value):
        if value is None:
            return value
        lower = value.lower()
        if lower not in {"low", "medium", "high", "urgent"}:
            raise ValueError("priority must be one of: low, medium, high, urgent")
        return lower

    @field_validator("status")
    @classmethod
    def validate_status(cls, value):
        if value is None:
            return value
        lower = value.lower()
        if lower not in {"open", "in_progress", "completed", "blocked", "review"}:
            raise ValueError("status must be one of: open, in_progress, completed, blocked, review")
        return lower
