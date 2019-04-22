import typing


class PullRequest:
    pass


class Push:
    pass


UNION_EVENTS = typing.Union[PullRequest, Push]

ALL_EVENTS = [PullRequest, Push]
