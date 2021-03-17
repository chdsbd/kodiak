from typing import Any

import django.http
import pydantic
from django.core.serializers.json import DjangoJSONEncoder


class PydanticJsonEncoder(DjangoJSONEncoder):
    """
    JSON encoder with Pydantic support.
    """

    def default(self, o: object) -> Any:
        if isinstance(o, pydantic.BaseModel):
            return o.dict()
        return super().default(o)


class JsonResponse(django.http.JsonResponse):
    """
    JSON response with Pydantic support.
    """

    def __init__(self, data: Any, **kwargs: Any):
        super().__init__(data, encoder=PydanticJsonEncoder, safe=False, **kwargs)
