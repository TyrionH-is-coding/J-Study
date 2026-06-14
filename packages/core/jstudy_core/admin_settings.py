from __future__ import annotations

from copy import deepcopy
import json
import tempfile
from pathlib import Path
from typing import Any

from packages.core.jstudy_core.providers import (
    DEFAULT_CHAT_MODEL,
    DEFAULT_EMBED_MODEL,
    SILICONFLOW_BASE_URL,
)


DEFAULT_SETTINGS_DIR_NAME = "data/settings"
MODEL_CATALOG_FILE = "model_catalog.json"
RUNTIME_FILE = "runtime.json"
CONTENT_PACK_FILE = "content_pack.json"
MNEMONICS_FILE = "mnemonics.json"


def _model_catalog_default() -> dict[str, Any]:
    return {
        "version": 1,
        "services": {
            "llm": {
                "active_profile_id": "llm-siliconflow",
                "active_model_id": "llm-default",
                "profiles": [
                    {
                        "id": "llm-siliconflow",
                        "name": "SiliconFlow Chat",
                        "binding": "siliconflow",
                        "base_url": SILICONFLOW_BASE_URL,
                        "api_key": "",
                        "api_key_path": "siliconflow api key.txt",
                        "api_version": "",
                        "extra_headers": {},
                        "models": [
                            {
                                "id": "llm-default",
                                "name": "Default Chat",
                                "model": DEFAULT_CHAT_MODEL,
                            }
                        ],
                    }
                ],
            },
            "embedding": {
                "active_profile_id": "embedding-siliconflow",
                "active_model_id": "embedding-default",
                "profiles": [
                    {
                        "id": "embedding-siliconflow",
                        "name": "SiliconFlow Embedding",
                        "binding": "siliconflow",
                        "base_url": SILICONFLOW_BASE_URL,
                        "api_key": "",
                        "api_key_path": "siliconflow api key.txt",
                        "api_version": "",
                        "extra_headers": {},
                        "models": [
                            {
                                "id": "embedding-default",
                                "name": "Default Embedding",
                                "model": DEFAULT_EMBED_MODEL,
                                "dimension": "",
                            }
                        ],
                    }
                ],
            },
            "search": {
                "active_profile_id": "search-disabled",
                "profiles": [
                    {
                        "id": "search-disabled",
                        "name": "Search Disabled",
                        "provider": "none",
                        "base_url": "",
                        "api_key": "",
                        "proxy": "",
                        "max_results": 5,
                        "models": [],
                    }
                ],
            },
        },
    }


def _runtime_default() -> dict[str, Any]:
    return {
        "version": 1,
        "rag": {
            "chunk_max_chars": 512,
            "chunk_overlap": 50,
            "top_k_candidates": 14,
            "per_query_limit": 2,
            "mnemonic_limit": 6,
        },
        "parser": {
            "backend": "pymupdf",
            "ocr": False,
            "tables": False,
            "formulas": False,
            "mineru": {
                "mode": "local",
                "api_base_url": "https://mineru.net",
                "api_token": "",
                "local_cli_path": "",
            },
        },
        "jobs": {
            "max_pdf_bytes": 50 * 1024 * 1024,
            "job_retention_hours": 0,
        },
    }


def _content_pack_default() -> dict[str, Any]:
    return {
        "version": 1,
        "active_pack_id": "medicine-default",
        "packs": [
            {
                "id": "medicine-default",
                "name": "Medicine MVP",
                "subject": "medicine",
                "soul_path": "soul.md",
                "mnemonics_path": "mnemonics.md",
                "mnemonics_json_path": f"{DEFAULT_SETTINGS_DIR_NAME}/mnemonics.json",
                "enabled": True,
            }
        ],
    }


def _mnemonics_default() -> dict[str, Any]:
    return {"version": 1, "items": []}


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=str(path.parent),
        delete=False,
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        tmp_path = Path(handle.name)
    tmp_path.replace(path)


def _json_object(path: Path) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _string(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _int(value: Any, default: int, minimum: int = 0) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    return max(minimum, parsed)


def _bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _active_profile(catalog: dict[str, Any], service_name: str) -> dict[str, Any] | None:
    service = catalog.get("services", {}).get(service_name, {})
    active_id = service.get("active_profile_id")
    profiles = service.get("profiles", [])
    for profile in profiles:
        if profile.get("id") == active_id:
            return profile
    return profiles[0] if profiles else None


def _active_model(catalog: dict[str, Any], service_name: str) -> dict[str, Any] | None:
    if service_name == "search":
        return None
    service = catalog.get("services", {}).get(service_name, {})
    profile = _active_profile(catalog, service_name)
    if not profile:
        return None
    active_id = service.get("active_model_id")
    models = profile.get("models", [])
    for model in models:
        if model.get("id") == active_id:
            return model
    return models[0] if models else None


def active_profile(catalog: dict[str, Any], service_name: str) -> dict[str, Any] | None:
    return _active_profile(catalog, service_name)


def active_model(catalog: dict[str, Any], service_name: str) -> dict[str, Any] | None:
    return _active_model(catalog, service_name)


def _normalize_model_catalog(catalog: dict[str, Any]) -> dict[str, Any]:
    base = _model_catalog_default()
    loaded_services = catalog.get("services", {}) if isinstance(catalog, dict) else {}
    base["version"] = 1
    for service_name, default_service in base["services"].items():
        service = loaded_services.get(service_name, {})
        profiles = service.get("profiles") if isinstance(service, dict) else None
        if isinstance(profiles, list) and profiles:
            default_service["profiles"] = profiles
        if isinstance(service, dict):
            default_service["active_profile_id"] = service.get(
                "active_profile_id",
                default_service.get("active_profile_id"),
            )
            if service_name != "search":
                default_service["active_model_id"] = service.get(
                    "active_model_id",
                    default_service.get("active_model_id"),
                )

        for index, profile in enumerate(default_service["profiles"]):
            profile.setdefault("id", f"{service_name}-profile-{index + 1}")
            profile.setdefault("name", "Profile")
            profile.setdefault("base_url", "")
            profile.setdefault("api_key", "")
            profile.setdefault("api_key_path", "")
            profile.setdefault("api_version", "")
            profile.setdefault("models", [])
            if service_name == "search":
                profile.setdefault("provider", "none")
                profile.setdefault("proxy", "")
                profile["max_results"] = _int(profile.get("max_results"), 5, minimum=1)
                profile["models"] = []
            else:
                profile.setdefault("binding", "siliconflow")
                profile.setdefault("extra_headers", {})
                for model_index, model in enumerate(profile["models"]):
                    model.setdefault("id", f"{service_name}-model-{model_index + 1}")
                    model.setdefault("name", model.get("model") or "Model")
                    model.setdefault("model", "")
                    if service_name == "embedding":
                        model.setdefault("dimension", "")

        profile_ids = {profile.get("id") for profile in default_service["profiles"]}
        if default_service["profiles"] and default_service.get("active_profile_id") not in profile_ids:
            default_service["active_profile_id"] = default_service["profiles"][0]["id"]
        if service_name != "search":
            profile = _active_profile(base, service_name)
            models = profile.get("models", []) if profile else []
            model_ids = {model.get("id") for model in models}
            if models and default_service.get("active_model_id") not in model_ids:
                default_service["active_model_id"] = models[0]["id"]
    return base


def _normalize_runtime(settings: dict[str, Any]) -> dict[str, Any]:
    default = _runtime_default()
    runtime = settings if isinstance(settings, dict) else {}
    rag = {**default["rag"], **(runtime.get("rag", {}) if isinstance(runtime.get("rag"), dict) else {})}
    parser = {
        **default["parser"],
        **(runtime.get("parser", {}) if isinstance(runtime.get("parser"), dict) else {}),
    }
    mineru = {
        **default["parser"]["mineru"],
        **(parser.get("mineru", {}) if isinstance(parser.get("mineru"), dict) else {}),
    }
    jobs = {
        **default["jobs"],
        **(runtime.get("jobs", {}) if isinstance(runtime.get("jobs"), dict) else {}),
    }
    chunk_max_chars = _int(rag.get("chunk_max_chars"), 512, minimum=1)
    chunk_overlap = _int(rag.get("chunk_overlap"), 50, minimum=0)
    if chunk_overlap >= chunk_max_chars:
        chunk_overlap = max(0, chunk_max_chars - 1)
    return {
        "version": 1,
        "rag": {
            "chunk_max_chars": chunk_max_chars,
            "chunk_overlap": chunk_overlap,
            "top_k_candidates": _int(rag.get("top_k_candidates"), 14, minimum=1),
            "per_query_limit": _int(rag.get("per_query_limit"), 2, minimum=1),
            "mnemonic_limit": _int(rag.get("mnemonic_limit"), 6, minimum=1),
        },
        "parser": {
            "backend": _string(parser.get("backend")) or "pymupdf",
            "ocr": _bool(parser.get("ocr"), False),
            "tables": _bool(parser.get("tables"), False),
            "formulas": _bool(parser.get("formulas"), False),
            "mineru": {
                "mode": _string(mineru.get("mode")) or "local",
                "api_base_url": _string(mineru.get("api_base_url")).rstrip("/") or "https://mineru.net",
                "api_token": _string(mineru.get("api_token")),
                "local_cli_path": _string(mineru.get("local_cli_path")),
            },
        },
        "jobs": {
            "max_pdf_bytes": _int(jobs.get("max_pdf_bytes"), 50 * 1024 * 1024, minimum=1),
            "job_retention_hours": _int(jobs.get("job_retention_hours"), 0, minimum=0),
        },
    }


def _normalize_content_pack(settings: dict[str, Any]) -> dict[str, Any]:
    default = _content_pack_default()
    content = settings if isinstance(settings, dict) else {}
    packs = content.get("packs") if isinstance(content.get("packs"), list) else default["packs"]
    normalized_packs = []
    for index, pack in enumerate(packs):
        if not isinstance(pack, dict):
            continue
        normalized_packs.append(
            {
                "id": _string(pack.get("id")) or f"content-pack-{index + 1}",
                "name": _string(pack.get("name")) or "Content Pack",
                "subject": _string(pack.get("subject")) or "medicine",
                "soul_path": _string(pack.get("soul_path")) or "soul.md",
                "mnemonics_path": _string(pack.get("mnemonics_path")) or "mnemonics.md",
                "mnemonics_json_path": _string(pack.get("mnemonics_json_path"))
                or f"{DEFAULT_SETTINGS_DIR_NAME}/mnemonics.json",
                "enabled": _bool(pack.get("enabled"), True),
            }
        )
    if not normalized_packs:
        normalized_packs = default["packs"]
    active_id = _string(content.get("active_pack_id")) or normalized_packs[0]["id"]
    if active_id not in {pack["id"] for pack in normalized_packs}:
        active_id = normalized_packs[0]["id"]
    return {"version": 1, "active_pack_id": active_id, "packs": normalized_packs}


def _normalize_mnemonics(settings: dict[str, Any]) -> dict[str, Any]:
    items = settings.get("items") if isinstance(settings, dict) else []
    normalized = []
    if isinstance(items, list):
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            normalized.append(
                {
                    "id": _string(item.get("id")) or f"mnemonic-{index + 1}",
                    "title": _string(item.get("title")) or "Untitled Mnemonic",
                    "subject": _string(item.get("subject")),
                    "topic": _string(item.get("topic")),
                    "tags": [str(tag).strip() for tag in item.get("tags", []) if str(tag).strip()]
                    if isinstance(item.get("tags"), list)
                    else [],
                    "content": _string(item.get("content")),
                    "notes": _string(item.get("notes")),
                    "enabled": _bool(item.get("enabled"), True),
                }
            )
    return {"version": 1, "items": normalized}


def render_mnemonics_markdown(settings: dict[str, Any]) -> str:
    mnemonics = _normalize_mnemonics(settings)
    blocks: list[str] = []
    for item in mnemonics["items"]:
        if not item["enabled"]:
            continue
        lines = [f"### {item['title']}", f"- ID: {item['id']}"]
        if item["subject"]:
            lines.append(f"- Subject: {item['subject']}")
        if item["topic"]:
            lines.append(f"- Topic: {item['topic']}")
        if item["tags"]:
            lines.append(f"- Tags: {', '.join(item['tags'])}")
        if item["notes"]:
            lines.append(f"- Notes: {item['notes']}")
        lines.append("")
        lines.append(item["content"])
        blocks.append("\n".join(lines).strip())
    return "\n\n".join(blocks)


def _resolve_project_path(project_root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return project_root / path


def active_content_pack(content_pack: dict[str, Any]) -> dict[str, Any]:
    active_id = content_pack.get("active_pack_id")
    for pack in content_pack.get("packs", []):
        if pack.get("id") == active_id:
            return pack
    packs = content_pack.get("packs", [])
    return packs[0] if packs else _content_pack_default()["packs"][0]


def redact_model_catalog(catalog: dict[str, Any]) -> dict[str, Any]:
    redacted = deepcopy(catalog)
    for service in redacted.get("services", {}).values():
        for profile in service.get("profiles", []):
            api_key = _string(profile.get("api_key"))
            profile["api_key_set"] = bool(api_key)
            profile["api_key"] = ""
    return redacted


def preserve_redacted_api_keys(
    incoming: dict[str, Any],
    existing: dict[str, Any],
) -> dict[str, Any]:
    merged = deepcopy(incoming)
    existing_keys: dict[tuple[str, str], str] = {}
    for service_name, service in existing.get("services", {}).items():
        for profile in service.get("profiles", []):
            existing_keys[(service_name, profile.get("id"))] = _string(profile.get("api_key"))

    for service_name, service in merged.get("services", {}).items():
        for profile in service.get("profiles", []):
            if profile.get("api_key") or not profile.get("api_key_set"):
                continue
            previous = existing_keys.get((service_name, profile.get("id")), "")
            if previous:
                profile["api_key"] = previous
            profile.pop("api_key_set", None)
    return merged


class AdminSettingsService:
    def __init__(self, settings_dir: Path):
        self.settings_dir = settings_dir

    def path_for(self, name: str) -> Path:
        return self.settings_dir / name

    def load_model_catalog(self) -> dict[str, Any]:
        return self._load_or_create(MODEL_CATALOG_FILE, _model_catalog_default(), _normalize_model_catalog)

    def save_model_catalog(self, catalog: dict[str, Any]) -> dict[str, Any]:
        return self._save(MODEL_CATALOG_FILE, _normalize_model_catalog(catalog))

    def load_runtime(self) -> dict[str, Any]:
        return self._load_or_create(RUNTIME_FILE, _runtime_default(), _normalize_runtime)

    def save_runtime(self, settings: dict[str, Any]) -> dict[str, Any]:
        return self._save(RUNTIME_FILE, _normalize_runtime(settings))

    def load_content_pack(self) -> dict[str, Any]:
        return self._load_or_create(CONTENT_PACK_FILE, _content_pack_default(), _normalize_content_pack)

    def save_content_pack(self, settings: dict[str, Any]) -> dict[str, Any]:
        return self._save(CONTENT_PACK_FILE, _normalize_content_pack(settings))

    def load_mnemonics(self) -> dict[str, Any]:
        return self._load_or_create(MNEMONICS_FILE, _mnemonics_default(), _normalize_mnemonics)

    def save_mnemonics(self, settings: dict[str, Any]) -> dict[str, Any]:
        return self._save(MNEMONICS_FILE, _normalize_mnemonics(settings))

    def load_all(self) -> dict[str, Any]:
        return {
            "settings_dir": str(self.settings_dir),
            "model_catalog": self.load_model_catalog(),
            "runtime": self.load_runtime(),
            "content_pack": self.load_content_pack(),
            "mnemonics": self.load_mnemonics(),
        }

    def save_all(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.save_model_catalog(payload.get("model_catalog", self.load_model_catalog()))
        self.save_runtime(payload.get("runtime", self.load_runtime()))
        self.save_content_pack(payload.get("content_pack", self.load_content_pack()))
        self.save_mnemonics(payload.get("mnemonics", self.load_mnemonics()))
        return self.load_all()

    def load_public(self) -> dict[str, Any]:
        payload = self.load_all()
        payload["model_catalog"] = redact_model_catalog(payload["model_catalog"])
        return payload

    def save_public(self, payload: dict[str, Any]) -> dict[str, Any]:
        incoming = deepcopy(payload)
        incoming["model_catalog"] = preserve_redacted_api_keys(
            incoming.get("model_catalog", {}),
            self.load_model_catalog(),
        )
        return self.save_all(incoming)

    def sync_mnemonics_markdown(self, project_root: Path) -> Path:
        content = self.load_content_pack()
        pack = active_content_pack(content)
        target = _resolve_project_path(project_root, pack["mnemonics_path"])
        markdown = render_mnemonics_markdown(self.load_mnemonics())
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((markdown or "# Mnemonics\n") + "\n", encoding="utf-8")
        return target

    def _load_or_create(
        self,
        file_name: str,
        default: dict[str, Any],
        normalizer: Any,
    ) -> dict[str, Any]:
        path = self.path_for(file_name)
        loaded = _json_object(path)
        normalized = normalizer({**default, **loaded}) if loaded else normalizer(default)
        if normalized != loaded:
            _atomic_write_json(path, normalized)
        return normalized

    def _save(self, file_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        _atomic_write_json(self.path_for(file_name), payload)
        return payload
