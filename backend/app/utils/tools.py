import json
from pathlib import Path
from typing import Any


def save_json(
    data: dict[str, Any] | list[Any],
    file_path: str | Path,
    *,
    indent: int | None = 2,
) -> Path:
    """Save JSON-compatible data as UTF-8, creating parent directories.

    Overwrites an existing file and returns its path. Convert model objects
    with model_dump(mode="json") before passing them to this function.
    Serialization and filesystem errors propagate to the caller.
    """
    serialized = json.dumps(data, indent=indent, ensure_ascii=False)
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialized, encoding="utf-8")
    return path
