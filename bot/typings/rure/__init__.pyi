from re import Match, RegexFlag
from typing import AnyStr, Optional, Pattern, overload

from rure import exceptions

__all__ = ["exceptions"]

_FlagsType = RegexFlag

@overload
def search(
    pattern: AnyStr, string: AnyStr, flags: _FlagsType = ...
) -> Optional[Match[AnyStr]]: ...
@overload
def search(
    pattern: Pattern[AnyStr], string: AnyStr, flags: _FlagsType = ...
) -> Optional[Match[AnyStr]]: ...
