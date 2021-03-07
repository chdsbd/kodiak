import django.http
import pydantic
from django.core.serializers.json import DjangoJSONEncoder


class PydanticJsonEncoder(DjangoJSONEncoder):
    def default(self, o):
        if isinstance(o, pydantic.BaseModel):
            return o.dict()
        return super().default(o)


class JsonResponse(django.http.JsonResponse):
    def __init__(self, data, **kwargs):
        super().__init__(data, encoder=PydanticJsonEncoder, safe=False, **kwargs)
