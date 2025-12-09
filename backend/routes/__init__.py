"""
API route modules.
"""

from .auth import router as auth_router
from .player import router as player_router
from .parent import router as parent_router
from .invites import router as invites_router
from .teams import router as teams_router
from .assignments import router as assignments_router
from .annotations import router as annotations_router
from .stats import router as stats_router

__all__ = [
    "auth_router",
    "player_router",
    "parent_router",
    "invites_router",
    "teams_router",
    "assignments_router",
    "annotations_router",
    "stats_router"
]
