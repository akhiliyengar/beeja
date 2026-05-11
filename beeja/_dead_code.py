"""Find public symbols in the manifest that are never referenced outside their module.

Usage:
    python -m beeja._dead_code

This is the cheap LSP-substitute for "find dead code". It walks the manifest,
greps the rest of the codebase for each name, and reports symbols with zero
external references. False positives are possible for symbols accessed
dynamically (getattr, plugin registries) — review before deleting.
"""

from __future__ import annotations

import re
from pathlib import Path

from beeja._manifest import generate_manifest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCAN_DIRS = ["beeja", "tests"]
# Symbols intentionally exported for external consumers; never report these.
PUBLIC_API_ALLOWLIST = {
    "main",            # console-script entry point
    "__init__",        # always referenced via construction
    "__version__",
    "load_manifest",   # used by CLI/MCP
    "write_manifest",  # used by CLI
    "generate_manifest",
}


def _iter_python_files() -> list[Path]:
    files: list[Path] = []
    for d in SCAN_DIRS:
        files.extend((REPO_ROOT / d).rglob("*.py"))
    return files


def _build_text_index() -> dict[Path, str]:
    return {f: f.read_text(encoding="utf-8") for f in _iter_python_files()}


def find_unused() -> list[tuple[str, str, str]]:
    """Return list of (module, kind, name) for symbols with no references at all.

    A reference counts if the name appears anywhere in the repo OTHER than its
    own definition line. This catches both cross-module and intra-module use,
    so a helper called only from within its defining module is NOT flagged.
    """
    manifest = generate_manifest()
    index = _build_text_index()
    unused: list[tuple[str, str, str]] = []

    for mod in manifest["modules"]:
        mod_name = mod["module"]
        mod_file = REPO_ROOT / mod["file"]
        mod_text = index.get(mod_file, "")

        for kind_key, kind in [("functions", "function"), ("classes", "class")]:
            for sym in mod[kind_key]:
                name = sym["name"]
                if name in PUBLIC_API_ALLOWLIST:
                    continue
                pattern = re.compile(rf"\b{re.escape(name)}\b")

                # Count references inside the defining module, EXCLUDING the
                # definition line itself.
                def_line_idx = sym["line"] - 1
                own_lines = mod_text.splitlines()
                own_hits = sum(
                    1 for i, line in enumerate(own_lines)
                    if i != def_line_idx and pattern.search(line)
                )

                # Count references in other files.
                external_hits = sum(
                    1 for path, text in index.items()
                    if path != mod_file and pattern.search(text)
                )

                if own_hits == 0 and external_hits == 0:
                    unused.append((mod_name, kind, name))

    return unused


if __name__ == "__main__":
    import sys
    results = find_unused()
    if not results:
        print("No unused public symbols found.")
        sys.exit(0)
    print(f"Found {len(results)} symbol(s) with no references:\n")
    for mod, kind, name in results:
        print(f"  {mod}.{name}  ({kind})")
    print("\nNote: review carefully — dynamic access (getattr, registries) is invisible to this scan.")
    sys.exit(1)
