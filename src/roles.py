from dataclasses import dataclass
from typing import Dict, List, Optional

import yaml


@dataclass
class Role:
    name: str
    enabled: bool
    objectives: List[str]
    focus_categories: List[str]
    focus_topics: List[str]
    additional_sources: List[str]


def load_roles(path: str = "roles.yaml") -> Dict[str, Role]:
    with open(path, "r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    roles: Dict[str, Role] = {}
    for name, payload in (raw.get("roles") or {}).items():
        roles[name] = Role(
            name=name,
            enabled=bool(payload.get("enabled", False)),
            objectives=list(payload.get("objectives") or []),
            focus_categories=list(payload.get("focus_categories") or []),
            focus_topics=list(payload.get("focus_topics") or []),
            additional_sources=list(payload.get("additional_sources") or []),
        )
    return roles


def get_role(name: str, roles: Dict[str, Role]) -> Optional[Role]:
    return roles.get(name)


def list_roles(roles: Dict[str, Role]) -> List[Role]:
    return list(roles.values())


def enabled_roles(roles: Dict[str, Role]) -> List[Role]:
    return [role for role in roles.values() if role.enabled]
