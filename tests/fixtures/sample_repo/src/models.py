"""Database models."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class User:
    """Represents a user in the system."""
    id: int
    username: str
    email: str
    created_at: datetime


@dataclass
class Post:
    """Represents a blog post."""
    id: int
    title: str
    body: str
    author_id: int
    created_at: datetime
