"""Routers HTTP de MS1."""

from services.ms1_auth.routers.auth import router_auth
from services.ms1_auth.routers.notificaciones import router_notificaciones

__all__ = ["router_auth", "router_notificaciones"]
