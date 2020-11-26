from __future__ import annotations

from django.db.models.manager import BaseManager
from django.db.models.query import QuerySet


def patch_django() -> None:
    for cls in (QuerySet, BaseManager):
        cls.__class_getitem__ = classmethod(lambda cls, *args, **kwargs: cls)  # type: ignore [attr-defined]
