"""Resolve canonical ROMA study conditions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REGISTRY = Path(__file__).with_name("condition_registry.json")


def load_registry() -> dict[str, Any]:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def resolve(name: str) -> dict[str, Any]:
    conditions = load_registry()["conditions"]
    try:
        return {"name": name, **conditions[name]}
    except KeyError as exc:
        raise ValueError(f"Unknown condition {name!r}; choose one of {', '.join(conditions)}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", nargs="?", help="Readable condition name")
    args = parser.parse_args()
    if args.name:
        print(json.dumps(resolve(args.name), indent=2))
    else:
        print(json.dumps(load_registry(), indent=2))


if __name__ == "__main__":
    main()
