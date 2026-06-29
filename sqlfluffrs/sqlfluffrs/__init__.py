"""Re-export all public symbols from the compiled sqlfluffrs extension module."""

from .sqlfluffrs import *  # noqa: F401, F403

__doc__ = sqlfluffrs.__doc__  # noqa: F405
if hasattr(sqlfluffrs, "__all__"):  # noqa: F405
    __all__ = sqlfluffrs.__all__  # noqa: F405
