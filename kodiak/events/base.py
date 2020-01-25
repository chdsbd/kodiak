import pydantic


class Installation(pydantic.BaseModel):
    id: int


class GithubEvent(pydantic.BaseModel):
    installation: Installation
