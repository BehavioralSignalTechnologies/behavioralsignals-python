import importlib
from importlib.metadata import PackageNotFoundError

import behavioralsignals


def test_version_falls_back_when_the_package_is_not_installed(monkeypatch):
    def not_installed(name):
        raise PackageNotFoundError(name)

    monkeypatch.setattr("importlib.metadata.version", not_installed)
    assert importlib.reload(behavioralsignals).__version__ == "unknown"
    monkeypatch.undo()
    importlib.reload(behavioralsignals)
