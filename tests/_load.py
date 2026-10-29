"""Load const.py and api.py as a package without Home Assistant installed."""
import importlib.util
import pathlib
import sys
import types


def load(root: pathlib.Path):
    pkg = types.ModuleType("gecoos_ac")
    pkg.__path__ = [str(root)]
    sys.modules["gecoos_ac"] = pkg
    for name in ("const", "api"):
        spec = importlib.util.spec_from_file_location(f"gecoos_ac.{name}", root / f"{name}.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
    return sys.modules["gecoos_ac.api"]
