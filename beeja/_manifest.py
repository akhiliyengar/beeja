"""Static code-navigation manifest.

Generates a compact JSON index of public symbols across the package so that
agents (and humans) can find the right function to read/edit without scanning
every file. Cheaper than an LSP, sufficient for targeted updates.

Run as a script to regenerate:
    python -m beeja._manifest

Or via the CLI:
    beeja --manifest          # print to stdout
    beeja --manifest --write  # rewrite beeja/_manifest.json
"""

from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path
from typing import Any

# Modules to index. Order is preserved in the output.
MODULES = [
    "beeja.ops",
    "beeja.builder",
    "beeja.backends",
    "beeja.mcp_server",
]

PKG_DIR       = Path(__file__).resolve().parent
MANIFEST_PATH = PKG_DIR / "_manifest.json"


def _doc_first_line(obj: Any) -> str:
    doc = inspect.getdoc(obj) or ""
    return doc.splitlines()[0].strip() if doc else ""


def _signature(obj: Any) -> str:
    try:
        return str(inspect.signature(obj))
    except (TypeError, ValueError):
        return ""


def _is_public(name: str) -> bool:
    return not name.startswith("_")


def _module_entry(module_name: str) -> dict[str, Any]:
    mod = importlib.import_module(module_name)
    mod_file = Path(inspect.getsourcefile(mod) or "").as_posix()
    try:
        rel_file = str(Path(mod_file).relative_to(PKG_DIR.parent).as_posix())
    except ValueError:
        rel_file = mod_file

    functions: list[dict[str, Any]] = []
    classes: list[dict[str, Any]] = []
    constants: list[str] = []

    for name, obj in inspect.getmembers(mod):
        if not _is_public(name):
            continue
        # Only include things actually defined in this module.
        defined_in = getattr(obj, "__module__", None)

        if inspect.isfunction(obj) and defined_in == module_name:
            try:
                line = inspect.getsourcelines(obj)[1]
            except (OSError, TypeError):
                line = 0
            functions.append({
                "name": name,
                "signature": _signature(obj),
                "doc": _doc_first_line(obj),
                "line": line,
            })
        elif inspect.isclass(obj) and defined_in == module_name:
            methods = []
            for mname, mobj in inspect.getmembers(obj, predicate=inspect.isfunction):
                if not _is_public(mname) and mname != "__init__":
                    continue
                methods.append({
                    "name": mname,
                    "signature": _signature(mobj),
                    "doc": _doc_first_line(mobj),
                })
            try:
                line = inspect.getsourcelines(obj)[1]
            except (OSError, TypeError):
                line = 0
            classes.append({
                "name": name,
                "doc": _doc_first_line(obj),
                "line": line,
                "methods": methods,
            })
        elif (
            not inspect.ismodule(obj)
            and not callable(obj)
            and not inspect.isclass(obj)
            and isinstance(obj, (str, int, float, bool, tuple))
        ):
            constants.append(name)

    return {
        "module": module_name,
        "file": rel_file,
        "doc": _doc_first_line(mod),
        "functions": sorted(functions, key=lambda f: f["line"]),
        "classes": sorted(classes, key=lambda c: c["line"]),
        "constants": sorted(constants),
    }


def generate_manifest() -> dict[str, Any]:
    """Build the manifest dict by introspecting MODULES."""
    from beeja import __version__
    return {
        "version": __version__,
        "modules": [_module_entry(m) for m in MODULES],
    }


def write_manifest(path: Path = MANIFEST_PATH) -> Path:
    """Write the manifest as pretty JSON to *path*.

    Uses ``write_bytes`` (not ``write_text``) so the file has stable LF line
    endings on every platform. Otherwise Windows would write CRLF, and CI's
    ``git diff --exit-code`` against a Linux-regenerated copy would fail.
    """
    data = generate_manifest()
    payload = (json.dumps(data, indent=2) + "\n").encode("utf-8")
    path.write_bytes(payload)
    return path


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    """Load the committed manifest. Generates if missing."""
    if not path.exists():
        return generate_manifest()
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    import sys
    if "--write" in sys.argv:
        out = write_manifest()
        print(f"wrote {out}")
    else:
        print(json.dumps(generate_manifest(), indent=2))
