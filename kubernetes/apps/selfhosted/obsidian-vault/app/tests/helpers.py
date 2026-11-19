"""Shared test helpers: load the job scripts in ../resources as modules (stdlib only).

The scripts read sys.argv and os.environ at import time (the vault folder, service URLs,
limits), so every import here happens with a fixed argv and an empty environment. None of
them does any work at import: main() only runs under `if __name__ == "__main__"`.
"""
import importlib
import importlib.util
import os
import pathlib
import sys
from unittest import mock

sys.dont_write_bytecode = True  # keep __pycache__ out of resources/

APP_DIR = pathlib.Path(__file__).resolve().parent.parent
RESOURCES = APP_DIR / "resources"

# librarian.py and processor.py are imported by the job scripts and rely on the importer
# having put this folder on sys.path, so the tests have to do the same.
if str(RESOURCES) not in sys.path:
    sys.path.insert(0, str(RESOURCES))


def _clean_import():
    """argv and environment as a job with nothing configured would see them."""
    return (mock.patch.object(sys, "argv", ["script.py", "/nonexistent-vault"]),
            mock.patch.dict(os.environ, {}, clear=True))


def load_module(name):
    """Import a module with an importable name (vaultlib, librarian)."""
    argv, env = _clean_import()
    with argv, env:
        return importlib.import_module(name)


def load_script(filename):
    """Import a script whose file name has a hyphen (reading-inbox.py) without running main()."""
    path = RESOURCES / filename
    name = "script_" + path.stem.replace("-", "_")
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    argv, env = _clean_import()
    with argv, env:
        spec.loader.exec_module(module)
    sys.modules[name] = module
    return module
