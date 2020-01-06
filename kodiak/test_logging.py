import json
import logging
from typing import Any, cast

import pytest
from requests import PreparedRequest, Request, Response

from kodiak.logging import (
    SentryLevel,
    SentryProcessor,
    add_request_info_processor,
    get_logging_level,
)

# MIT License

# Copyright (c) 2019 Kiwi.com

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


def test_sentry_sent() -> None:
    processor = SentryProcessor()
    event_dict = processor(None, "error", {})
    assert "sentry_id" in event_dict


@pytest.mark.parametrize("level", ["debug", "info", "warning"])
def test_sentry_log(mocker: Any, level: SentryLevel) -> None:
    m_capture_event = mocker.patch("kodiak.logging.capture_event")

    event_data = {"event": level + " message"}
    sentry_event_data = event_data.copy()
    processor = SentryProcessor(level=getattr(logging, level.upper()))
    processor(None, level, event_data)

    m_capture_event.assert_called_once_with(
        {"level": level, "message": event_data["event"], "extra": sentry_event_data},
        hint={},
    )

    processor_only_errors = SentryProcessor(level=logging.ERROR)
    event_dict = processor_only_errors(None, level, {"event": level + " message"})

    assert "sentry_id" not in event_dict


@pytest.mark.parametrize("level", ["error", "critical"])
def test_sentry_log_failure(mocker: Any, level: SentryLevel) -> None:
    m_capture_event = mocker.patch("kodiak.logging.capture_event")
    mocker.patch(
        "kodiak.logging.event_from_exception",
        return_value=({"exception": mocker.sentinel.exception}, mocker.sentinel.hint),
    )

    event_data = {"event": level + " message"}
    sentry_event_data = event_data.copy()
    processor = SentryProcessor(level=getattr(logging, level.upper()))
    try:
        1 / 0
    except ZeroDivisionError:
        processor(None, level, event_data)

    m_capture_event.assert_called_once_with(
        {
            "level": level,
            "message": event_data["event"],
            "exception": mocker.sentinel.exception,
            "extra": sentry_event_data,
        },
        hint=mocker.sentinel.hint,
    )


@pytest.mark.parametrize("level", ["debug", "info", "warning"])
def test_sentry_log_all_as_tags(mocker: Any, level: SentryLevel) -> None:
    m_capture_event = mocker.patch("kodiak.logging.capture_event")

    event_data = {"event": level + " message"}
    sentry_event_data = event_data.copy()
    processor = SentryProcessor(
        level=getattr(logging, level.upper()), tag_keys="__all__"
    )
    processor(None, level, event_data)

    m_capture_event.assert_called_once_with(
        {
            "level": level,
            "message": event_data["event"],
            "extra": sentry_event_data,
            "tags": sentry_event_data,
        },
        hint={},
    )

    processor_only_errors = SentryProcessor(level=logging.ERROR)
    event_dict = processor_only_errors(None, level, {"event": level + " message"})

    assert "sentry_id" not in event_dict


@pytest.mark.parametrize("level", ["debug", "info", "warning"])
def test_sentry_log_specific_keys_as_tags(mocker: Any, level: SentryLevel) -> None:
    m_capture_event = mocker.patch("kodiak.logging.capture_event")

    event_data = {"event": level + " message", "info1": "info1", "required": True}
    tag_keys = ["info1", "required", "some non existing key"]
    sentry_event_data = event_data.copy()
    processor = SentryProcessor(
        level=getattr(logging, level.upper()), tag_keys=tag_keys
    )
    processor(None, level, event_data)

    m_capture_event.assert_called_once_with(
        {
            "level": level,
            "message": event_data["event"],
            "extra": sentry_event_data,
            "tags": {
                k: sentry_event_data[k] for k in tag_keys if k in sentry_event_data
            },
        },
        hint={},
    )

    processor_only_errors = SentryProcessor(level=logging.ERROR)
    event_dict = processor_only_errors(None, level, {"event": level + " message"})

    assert "sentry_id" not in event_dict


@pytest.mark.parametrize(
    "level,expected", [("info", logging.INFO), ("Warn", logging.WARN)]
)
def test_get_logging_level(level: str, expected: int) -> None:
    assert get_logging_level(level) == expected


# end of copied code
#####################################################


def test_add_request_info_processor() -> None:
    url = "https://api.example.com/v1/me"
    payload = dict(user_id=54321)
    req = Request("POST", url, json=payload)
    res = Response()
    res.status_code = 500
    res.url = url
    res.reason = "Internal Server Error"
    cast(
        Any, res
    )._content = b"Your request could not be completed due to an internal error."
    res.request = cast(PreparedRequest, req.prepare())  # type: ignore
    event_dict = add_request_info_processor(
        None, None, dict(event="request failed", res=res)
    )
    assert event_dict["response_content"] == cast(Any, res)._content
    assert event_dict["response_status_code"] == res.status_code
    assert event_dict["request_body"] == json.dumps(payload).encode()
    assert event_dict["request_url"] == req.url
    assert event_dict["request_method"] == "POST"
    assert event_dict["res"] is res
