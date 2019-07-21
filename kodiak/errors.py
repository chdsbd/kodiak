from dataclasses import dataclass

from requests_async import Response


class KodiakException(Exception):
    """
    base Kodiak Exception to make catching all Kodiak related exceptions
    easier
    """


class Queueable(KodiakException):
    pass


# TODO(sbdchd): do these need to inherit from Queueable?


class MissingGithubMergeabilityState(Queueable):
    """Github hasn't evaluated if this PR can be merged without conflicts yet"""


class NeedsBranchUpdate(Queueable):
    pass


class WaitingForChecks(Queueable):
    pass


class NotQueueable(KodiakException):
    pass


class MissingAppID(KodiakException):
    """
    Application app_id doesn't match configuration

    We do _not_ want to display this message to users as it could clobber
    another instance of kodiak.
    """

    def __str__(self) -> str:
        return "missing Github app id"


class BranchMerged(KodiakException):
    """branch has already been merged"""

    def __str__(self) -> str:
        return str(self.__doc__)


class MergeConflict(KodiakException):
    """Merge conflict in the PR."""

    def __str__(self) -> str:
        return "merge conflict"


@dataclass
class ServerError(KodiakException):
    response: Response
