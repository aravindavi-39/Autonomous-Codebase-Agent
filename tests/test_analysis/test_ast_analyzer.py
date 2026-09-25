"""Tests for Python AST analysis without executing code."""

import pytest
from pathlib import Path

from analysis.ast_analyzer import PythonASTAnalyzer
from ingestion.models import Language


@pytest.fixture
def analyzer() -> PythonASTAnalyzer:
    return PythonASTAnalyzer()


class TestFunctionAnalysis:
    """Verify function parsing and metadata extraction."""

    def test_simple_function(self, analyzer: PythonASTAnalyzer) -> None:
        code = '''
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b
'''
        analysis = analyzer.analyze_source(code, "math_utils.py")
        assert analysis.status == "ok"
        assert len(analysis.functions) == 1
        fn = analysis.functions[0]
        assert fn.name == "add"
        assert fn.file == "math_utils.py"
        assert fn.start_line == 2
        assert fn.end_line == 4
        assert fn.docstring == "Add two numbers."
        assert fn.return_annotation == "int"
        assert len(fn.parameters) == 2
        assert fn.parameters[0].name == "a"
        assert fn.parameters[0].annotation == "int"
        assert fn.parameters[1].name == "b"
        assert fn.parameters[1].annotation == "int"

    def test_function_parameters_and_defaults(self, analyzer: PythonASTAnalyzer) -> None:
        code = '''
def configure(host: str = "localhost", port: int = 8080, *args, timeout: float = 5.0, **kwargs) -> bool:
    return True
'''
        analysis = analyzer.analyze_source(code, "config.py")
        fn = analysis.functions[0]
        params = fn.parameters
        assert len(params) == 5

        # host
        assert params[0].name == "host"
        assert params[0].default == "'localhost'"
        assert params[0].kind == "positional_or_keyword"

        # port
        assert params[1].name == "port"
        assert params[1].default == "8080"
        assert params[1].kind == "positional_or_keyword"

        # *args
        assert params[2].name == "args"
        assert params[2].kind == "var_positional"

        # timeout
        assert params[3].name == "timeout"
        assert params[3].default == "5.0"
        assert params[3].kind == "keyword_only"

        # **kwargs
        assert params[4].name == "kwargs"
        assert params[4].kind == "var_keyword"

    def test_async_function(self, analyzer: PythonASTAnalyzer) -> None:
        code = '''
async def fetch_data(url: str):
    await client.get(url)
'''
        analysis = analyzer.analyze_source(code, "network.py")
        fn = analysis.functions[0]
        assert fn.name == "fetch_data"
        assert fn.is_async is True

    def test_nested_functions(self, analyzer: PythonASTAnalyzer) -> None:
        code = '''
def outer(x):
    def inner(y):
        return y * 2
    return inner(x)
'''
        analysis = analyzer.analyze_source(code, "nested.py")
        assert len(analysis.functions) == 1
        outer_fn = analysis.functions[0]
        assert outer_fn.name == "outer"
        assert len(outer_fn.nested_functions) == 1
        inner_fn = outer_fn.nested_functions[0]
        assert inner_fn.name == "inner"
        assert len(inner_fn.parameters) == 1
        assert inner_fn.parameters[0].name == "y"


class TestClassAnalysis:
    """Verify class structure, inheritance, methods, and attributes."""

    def test_class_definition_and_inheritance(self, analyzer: PythonASTAnalyzer) -> None:
        code = '''
class BaseService:
    pass

class UserService(BaseService, auth.AuthProvider):
    """User management service."""
    version: str = "1.0"
    
    def __init__(self, db):
        self.db = db
        
    def get_user(self, user_id: int):
        return self.db.find(user_id)
'''
        analysis = analyzer.analyze_source(code, "services.py")
        assert len(analysis.classes) == 2
        base = analysis.classes[0]
        assert base.name == "BaseService"
        assert base.base_classes == []

        user_svc = analysis.classes[1]
        assert user_svc.name == "UserService"
        assert user_svc.base_classes == ["BaseService", "auth.AuthProvider"]
        assert user_svc.docstring == "User management service."
        assert len(user_svc.methods) == 2
        assert user_svc.methods[0].name == "__init__"
        assert user_svc.methods[0].is_method is True
        assert user_svc.methods[1].name == "get_user"
        assert user_svc.methods[1].is_method is True

        # Class attributes
        assert len(user_svc.attributes) >= 1
        assert user_svc.attributes[0].name == "version"
        assert user_svc.attributes[0].annotation == "str"
        assert user_svc.attributes[0].value == "'1.0'"

    def test_class_and_method_decorators(self, analyzer: PythonASTAnalyzer) -> None:
        code = '''
@dataclass
class Point:
    x: int
    y: int

    @property
    def magnitude(self) -> float:
        return (self.x**2 + self.y**2)**0.5

    @classmethod
    def origin(cls):
        return cls(0, 0)
'''
        analysis = analyzer.analyze_source(code, "geom.py")
        cls = analysis.classes[0]
        assert len(cls.decorators) == 1
        assert cls.decorators[0].name == "dataclass"

        methods = {m.name: m for m in cls.methods}
        assert methods["magnitude"].decorators[0].name == "property"
        assert methods["origin"].decorators[0].name == "classmethod"


class TestImportsExtraction:
    """Verify import statements extraction and line preservation."""

    def test_various_imports(self, analyzer: PythonASTAnalyzer) -> None:
        code = '''
import os
import sys as system
from pathlib import Path, PurePath
from ..database import session as db_session
import requests
'''
        analysis = analyzer.analyze_source(
            code,
            "main.py",
            local_modules={"database"},
        )
        imports = analysis.imports
        assert len(imports) == 6

        # import os
        assert imports[0].module == "os"
        assert imports[0].alias is None
        assert imports[0].is_from_import is False
        assert imports[0].category == "stdlib"

        # import sys as system
        assert imports[1].module == "sys"
        assert imports[1].alias == "system"
        assert imports[1].category == "stdlib"

        # from pathlib import Path
        assert imports[2].module == "pathlib"
        assert imports[2].name == "Path"
        assert imports[2].is_from_import is True
        assert imports[2].category == "stdlib"

        # from pathlib import PurePath
        assert imports[3].module == "pathlib"
        assert imports[3].name == "PurePath"

        # from ..database import session as db_session (relative)
        assert imports[4].is_relative is True
        assert imports[4].name == "session"
        assert imports[4].alias == "db_session"
        assert imports[4].category == "local"

        # import requests
        assert imports[5].module == "requests"
        assert imports[5].category == "third_party"


class TestCallsAndExceptions:
    """Verify function calls and raised exceptions extraction."""

    def test_calls_and_exceptions(self, analyzer: PythonASTAnalyzer) -> None:
        code = '''
def process_order(order_id: int):
    logger.info("Processing order", order_id)
    if order_id < 0:
        raise ValueError("Invalid order id")
    database.save_user()
    validate()
'''
        analysis = analyzer.analyze_source(code, "orders.py")
        fn = analysis.functions[0]
        targets = [c.target for c in fn.calls]
        assert "logger.info" in targets
        assert "database.save_user" in targets
        assert "validate" in targets

        assert len(fn.exceptions_raised) == 1
        assert fn.exceptions_raised[0].exception_type == "ValueError"

    def test_module_level_calls(self, analyzer: PythonASTAnalyzer) -> None:
        code = '''
print("Starting application")
app = create_app()
app.run(debug=True)
'''
        analysis = analyzer.analyze_source(code, "entry.py")
        call_targets = [c.target for c in analysis.calls]
        assert "print" in call_targets
        assert "create_app" in call_targets
        assert "app.run" in call_targets


class TestSafetyAndErrorHandling:
    """Verify analyzer never executes code and handles errors gracefully."""

    def test_syntax_error_does_not_crash(self, analyzer: PythonASTAnalyzer) -> None:
        bad_code = "def broken(:"
        analysis = analyzer.analyze_source(bad_code, "broken.py")
        assert analysis.status == "parse_error"
        assert analysis.error_message is not None
        assert analysis.error_line == 1
        assert analysis.functions == []

    def test_empty_source(self, analyzer: PythonASTAnalyzer) -> None:
        analysis = analyzer.analyze_source("", "empty.py")
        assert analysis.status == "ok"
        assert analysis.functions == []
        assert analysis.classes == []

    def test_comments_only(self, analyzer: PythonASTAnalyzer) -> None:
        analysis = analyzer.analyze_source("# Just a comment\n# Another one\n", "comments.py")
        assert analysis.status == "ok"
        assert len(analysis.functions) == 0

    def test_unicode_source(self, analyzer: PythonASTAnalyzer) -> None:
        code = '''
def greet(name: str) -> str:
    """Salutations! 🚀 café, mañana, 日本語"""
    return f"Bonjour, {name}!"
'''
        analysis = analyzer.analyze_source(code, "unicode.py")
        assert analysis.status == "ok"
        assert "🚀" in analysis.functions[0].docstring

    def test_missing_file_handled(self, analyzer: PythonASTAnalyzer, tmp_path: Path) -> None:
        missing = tmp_path / "does_not_exist.py"
        analysis = analyzer.analyze_file(missing, "does_not_exist.py")
        assert analysis.status == "read_error"
        assert "Could not read file" in analysis.error_message
