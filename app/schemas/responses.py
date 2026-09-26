from typing import Literal

from pydantic import BaseModel


class HealthStatus(BaseModel):
    status: Literal["ok", "ready", "unavailable"]


class NotificationCounts(BaseModel):
    notifications: int
    messages: int


class Suggestion(BaseModel):
    title: str
    url: str


class PolledMessage(BaseModel):
    id: int
    body: str
    mine: bool
    sender: str
    created_at: str
    read: bool


class MessagePoll(BaseModel):
    messages: list[PolledMessage]
