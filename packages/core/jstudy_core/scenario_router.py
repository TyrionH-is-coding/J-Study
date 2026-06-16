from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ScenarioRoutingError(ValueError):
    pass


@dataclass(frozen=True)
class ScenarioResolution:
    requested_scenario_id: str
    scenario_id: str
    scenario: dict[str, Any]
    content_pack: dict[str, Any]
    soul_profile: dict[str, Any]

    def trace_metadata(self) -> dict[str, Any]:
        return {
            "requested_scenario_id": self.requested_scenario_id,
            "resolved_scenario_id": self.scenario_id,
            "content_pack_id": self.content_pack.get("id", ""),
            "prompt_profile": self.scenario.get("prompt_profile", ""),
            "soul_profile_id": self.soul_profile.get("id", ""),
            "rag_profile": self.scenario.get("rag_profile", ""),
            "domain_rules": self.scenario.get("domain_rules", []),
        }


def resolve_scenario(
    content_config: dict[str, Any],
    requested_scenario_id: str | None = None,
) -> ScenarioResolution:
    requested = (requested_scenario_id or "").strip()
    selected_id = requested or str(
        content_config.get("default_scenario_id") or content_config.get("active_pack_id") or ""
    )
    scenario = next(
        (item for item in content_config.get("scenarios", []) if item.get("id") == selected_id),
        None,
    )
    if scenario is None:
        raise ScenarioRoutingError(f"Unknown scenario_id: {selected_id}")
    if not scenario.get("enabled", True):
        raise ScenarioRoutingError(f"Scenario is disabled: {selected_id}")

    pack_id = str(scenario.get("content_pack_id") or content_config.get("active_pack_id") or "")
    pack = next((item for item in content_config.get("packs", []) if item.get("id") == pack_id), None)
    if pack is None:
        raise ScenarioRoutingError(f"Scenario content pack not found: {pack_id}")
    if not pack.get("enabled", True):
        raise ScenarioRoutingError(f"Scenario content pack is disabled: {pack_id}")

    prompt_profile = str(scenario.get("prompt_profile") or "")
    soul_profile = next(
        (item for item in content_config.get("soul_profiles", []) if item.get("id") == prompt_profile),
        None,
    )
    if soul_profile is None:
        soul_profile = {
            "id": prompt_profile or pack_id,
            "name": prompt_profile or pack_id,
            "subject": scenario.get("subject") or pack.get("subject") or "",
            "soul_path": pack.get("soul_path", ""),
            "notes": "",
        }

    return ScenarioResolution(
        requested_scenario_id=requested,
        scenario_id=selected_id,
        scenario=scenario,
        content_pack=pack,
        soul_profile=soul_profile,
    )
