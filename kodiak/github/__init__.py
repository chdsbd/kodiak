import typing
from dataclasses import dataclass
from collections import defaultdict

from fastapi import FastAPI, Header, HTTPException
from starlette import status
from kodiak.github import events
from kodiak.github.events import ALL_EVENTS, UNION_EVENTS


def valid_event(arg: typing.Any) -> bool:
    return arg in ALL_EVENTS


class UnsupportType(TypeError):
    def __init__(self, annotation: str):
        return super().__init__(
            f"Invalid type annotation: '{annotation}'. Only `github.events` types are valid in Union."
        )


@dataclass(init=False)
class Webhook:

    event_mapping: typing.Mapping[UNION_EVENTS, typing.List[typing.Callable]]

    def __init__(self, app: FastAPI, path="/api/github/hook"):
        self.event_mapping: typing.Mapping[
            UNION_EVENTS, typing.List[typing.Callable]
        ] = defaultdict(list)

        app.add_api_route(path=path, endpoint=self._api_handler, methods=["POST"])

    async def _api_handler(self, event: dict, *, x_github_event: str = Header(None)):
        """
        Handler for all Github api payloads
        
        We run webhook events that hit this endpoint against events registered
        in `event_mapping`.
        """
        # FastAPI allows x_github_event to be nullable and we cannot type it as
        # Optional in the function definition
        # https://github.com/tiangolo/fastapi/issues/179
        github_event = typing.cast(typing.Optional[str], x_github_event)
        if github_event is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required header: X-Github-Event",
            )
        handler = events.event_registry.get(github_event)
        if handler is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Event '{github_event}' has no registered handler. Support likely doesn't exist for this kind of event.",
            )
        listeners = self.event_mapping.get(handler)
        if listeners is None:
            return {"msg": "no listeners"}
        for listener in listeners:
            listener(handler.parse_obj(event))
        return {"msg": "ok"}

    def register_events(self, func: typing.Callable, events: typing.List[UNION_EVENTS]):
        for event in events:
            self.event_mapping[event].append(func)

    def __call__(self) -> typing.Callable:
        def decorator(func: typing.Callable[[events.PullRequestEvent], None]):
            arg_count = func.__code__.co_argcount
            annotations = typing.get_type_hints(func)
            if arg_count != 1 or len(annotations) != 1:
                raise TypeError(
                    f"invalid number of arguments '{arg_count}'. Only one argument should be provided."
                )
            # we will only have one argument/annotation at this point
            typehints = list(annotations.values())[0]

            # we have a union of types
            if getattr(typehints, "__origin__", None) == typing.Union:
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
