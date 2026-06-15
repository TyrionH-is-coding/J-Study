from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ParserProfileRoutingError(ValueError):
    pass


class ParserProfileUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class ParserProfileResolution:
    requested_profile_id: str
    profile_id: str
    display_name: str
    backend: str
    tier: str
    visible_to_users: bool
    requires_admin: bool

    def trace_metadata(self) -> dict[str, Any]:
        return {
            "requested_parser_profile_id": self.requested_profile_id,
            "resolved_parser_profile_id": self.profile_id,
            "display_name": self.display_name,
            "backend": self.backend,
            "tier": self.tier,
            "visible_to_users": self.visible_to_users,
            "requires_admin": self.requires_admin,
        }


def public_parser_profiles(config: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": profile.get("id", ""),
            "display_name": profile.get("display_name", ""),
            "estimated_wait": profile.get("estimated_wait", ""),
            "tier": profile.get("tier", ""),
        }
        for profile in config.get("profiles", [])
        if profile.get("enabled", True)
        and profile.get("visible_to_users", False)
        and not profile.get("requires_admin", False)
    ]


def resolve_parser_profile(
    config: dict[str, Any],
    requested_profile_id: str | None = None,
    is_admin: bool = False,
    parser_config: dict[str, Any] | None = None,
) -> ParserProfileResolution:
    requested = (requested_profile_id or "").strip()
    selected_id = requested or str(config.get("default_profile_id") or "fast")
    profile = next((item for item in config.get("profiles", []) if item.get("id") == selected_id), None)
    if profile is None:
        raise ParserProfileRoutingError(f"Unknown parser_profile_id: {selected_id}")
    if not profile.get("enabled", True):
        raise ParserProfileRoutingError(f"Parser profile is disabled: {selected_id}")
    if profile.get("requires_admin", False) and not is_admin:
        raise ParserProfileRoutingError(f"Parser profile requires admin access: {selected_id}")
    if not profile.get("visible_to_users", False) and not is_admin:
        raise ParserProfileRoutingError(f"Parser profile is not available: {selected_id}")

    backend = str(profile.get("backend") or "pymupdf")
    if backend == "mineru" and parser_config is not None and not _mineru_configured(parser_config):
        raise ParserProfileUnavailable("MinerU is not configured; use fast parsing for now")

    return ParserProfileResolution(
        requested_profile_id=requested,
        profile_id=selected_id,
        display_name=str(profile.get("display_name") or selected_id),
        backend=backend,
        tier=str(profile.get("tier") or ""),
        visible_to_users=bool(profile.get("visible_to_users", False)),
        requires_admin=bool(profile.get("requires_admin", False)),
    )


def _mineru_configured(parser_config: dict[str, Any]) -> bool:
    mineru = parser_config.get("mineru", {}) if isinstance(parser_config.get("mineru"), dict) else {}
    return bool(
        str(mineru.get("api_token") or "").strip()
        or str(mineru.get("local_cli_path") or "").strip()
    )
