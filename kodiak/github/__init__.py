import typing
from dataclasses import dataclass
from collections import defaultdict
from fastapi import FastAPI
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
    app: FastAPI

    event_mapping: typing.Mapping[UNION_EVENTS, typing.List[typing.Callable]]

    def __init__(self, app: FastAPI):
        self.app = app
        self.event_mapping = defaultdict(list)

    def register_events(self, func: typing.Callable, events: typing.List[UNION_EVENTS]):
        for event in events:
            self.event_mapping[event].append(func)

    def __call__(self) -> typing.Callable:
        def decorator(func: typing.Callable[[events.PullRequest], None]):
            arg_count = func.__code__.co_argcount
            annotations = typing.get_type_hints(func)
            if arg_count != 1 or len(annotations) != 1:
                raise TypeError(
                    f"invalid number of arguments '{arg_count}'. Only one argument should be provided."
                )
            # we will only have one argument/annotation at this point
            typehints = list(annotations.values())[0]

            # TODO: Move checks to register_events function
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
