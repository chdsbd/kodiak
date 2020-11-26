from __future__ import annotations

from django.db.models.manager import BaseManager
from django.db.models.query import QuerySet


def patch_django() -> None:
    """
    On Django versions < 3.1 we need to monkey patch the class get item
    method so that we can type QuerySet and Managers with a generic argument.
    """
    for cls in (QuerySet, BaseManager):
        cls.__class_getitem__ = classmethod(lambda cls, *args, **kwargs: cls)  # type: ignore [attr-defined]
