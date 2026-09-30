import importlib


def test_imports_and_public_exports():
    mod = importlib.import_module("calm")
    api = importlib.import_module("calm.api")

    # Basic sanity checks
    assert hasattr(mod, "__file__")
    assert isinstance(api.PUBLIC_EXPORTS, (list, tuple))
    assert len(api.PUBLIC_EXPORTS) > 0

    # __version__ should be present and be a string
    assert hasattr(mod, "__version__")
    assert isinstance(mod.__version__, str)
