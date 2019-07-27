import hashlib
import hmac
import inspect
from collections import defaultdict
from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    List,
    MutableMapping,
    Optional,
    Type,
    Union,
    cast,
    get_type_hints,
)

import structlog
from fastapi import FastAPI, Header, HTTPException
from starlette import status
from starlette.config import Config
from starlette.requests import Request

from kodiak.github import events

config = Config(".env")
SECRET_KEY = config("SECRET_KEY")

log = structlog.get_logger()


def valid_event(arg: Any) -> bool:
    return arg in events.event_registry.values()


class UnsupportType(TypeError):
    def __init__(self, annotation: str):
        super().__init__(
            f"Invalid type annotation: '{annotation}'. Only `github.events` types are valid in Union."
        )


DecoratorFunc = Union[
    Callable[[events.GithubEvent], None], Callable[[Union[events.GithubEvent]], None]
]


@dataclass(init=False)
class Webhook:

    event_mapping: MutableMapping[Type[events.GithubEvent], List[Callable]]

    def __init__(self, app: FastAPI, path: str = "/api/github/hook"):
        self.event_mapping = defaultdict(list)

        app.add_api_route(path=path, endpoint=self._api_handler, methods=["POST"])

    async def _api_handler(
        self,
        event: dict,
        *,
        request: Request,
        x_github_event: str = Header(None),
        x_hub_signature: str = Header(None),
    ) -> None:
        """
        Handler for all Github api payloads

        We run webhook events that hit this endpoint against events registered
        in `event_mapping`.
        """
        # FastAPI allows x_github_event to be nullable and we cannot type it as
        # Optional in the function definition
        # https://github.com/tiangolo/fastapi/issues/179
        github_event = cast(Optional[str], x_github_event)
        github_signature = cast(Optional[str], x_hub_signature)
        expected_sha = hmac.new(
            key=SECRET_KEY.encode(), msg=(await request.body()), digestmod=hashlib.sha1
        ).hexdigest()
        if github_event is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required header: X-Github-Event",
            )
        if github_signature is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required signature: X-Hub-Signature",
            )
        sha = github_signature.replace("sha1=", "")
        if not hmac.compare_digest(sha, expected_sha):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid signature: X-Hub-Signature",
            )
        handler = events.event_registry.get(github_event)
        if handler is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Event '{github_event}' has no registered handler. Support likely doesn't exist for this kind of event.",
            )
        listeners = self.event_mapping.get(handler)
        bound_log = log.bind(github_event=github_event)
        if listeners is None:
            bound_log.info("No event listeners registered")
            return None
        bound_log.info("Processing listeners for event", listener_count=len(listeners))
        for listener in listeners:
            res = listener(handler.parse_obj(event))
            # support async and non-async functions
            if inspect.isawaitable(res):
                await res
        return None

    def register_events(
        self, func: Callable, events: List[Type[events.GithubEvent]]
    ) -> None:
        for event in events:
            self.event_mapping[event].append(func)

    def __call__(self) -> Callable:
        def decorator(func: DecoratorFunc) -> DecoratorFunc:
            arg_count = func.__code__.co_argcount
            annotations = get_type_hints(func)
            if arg_count != 1 or len(annotations) not in {1, 2}:
                raise TypeError(
                    f"invalid number of arguments '{arg_count}'. Only one argument should be provided."
                )
            # we will only have one argument/annotation at this point
            typehints = list(annotations.values())[0]

            # we have a union of types
            if getattr(typehints, "__origin__", None) == Union:
                for type in typehints.__args__:
                    if not valid_event(type):
                        raise UnsupportType(typehints)
                self.register_events(func, typehints.__args__)
            # we have one event
            elif valid_event(typehints):
                self.register_events(func, [typehints])
            # we have an unrecognized type
            else:
                raise UnsupportType(typehints)

            return func

        return decorator
