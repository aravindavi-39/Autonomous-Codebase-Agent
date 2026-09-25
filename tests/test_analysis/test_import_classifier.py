"""Tests for import classification without network requests."""

import pytest

from analysis.import_classifier import classify_import


class TestImportClassifier:
    """Verify stdlib, local, and third-party import classification."""

    @pytest.mark.parametrize(
        "module",
        [
            "os",
            "sys",
            "pathlib",
            "ast",
            "json",
            "typing",
            "dataclasses",
            "datetime",
            "hashlib",
            "collections",
            "itertools",
            "functools",
            "subprocess",
            "re",
            "shutil",
            "tempfile",
        ],
    )
    def test_stdlib_imports(self, module: str) -> None:
        """Standard library modules should be classified as 'stdlib'."""
        assert classify_import(module) == "stdlib"

    def test_submodule_stdlib(self) -> None:
        """Submodules of stdlib (e.g. os.path, collections.abc) are stdlib."""
        assert classify_import("os.path") == "stdlib"
        assert classify_import("collections.abc") == "stdlib"
        assert classify_import("urllib.parse") == "stdlib"

    def test_relative_import_is_local(self) -> None:
        """Relative imports with leading dot or empty module are local."""
        assert classify_import("", is_relative=True) == "local"
        assert classify_import("models", is_relative=True) == "local"

    def test_local_module_detection(self) -> None:
        """Modules matching local project packages/modules are 'local'."""
        local_mods = {"src", "models", "utils", "api"}
        assert classify_import("src.app", local_modules=local_mods) == "local"
        assert classify_import("models", local_modules=local_mods) == "local"
        assert classify_import("utils.helpers", local_modules=local_mods) == "local"

    def test_third_party_imports(self) -> None:
        """Packages neither in stdlib nor in local_modules are 'third_party'."""
        assert classify_import("flask") == "third_party"
        assert classify_import("pydantic") == "third_party"
        assert classify_import("pytest") == "third_party"
        assert classify_import("numpy") == "third_party"
        assert classify_import("requests.auth") == "third_party"

    def test_local_takes_priority_over_third_party(self) -> None:
        """If a package name is in local_modules, it is classified as local."""
        assert classify_import("custom_lib", local_modules={"custom_lib"}) == "local"
        assert classify_import("custom_lib", local_modules=None) == "third_party"
