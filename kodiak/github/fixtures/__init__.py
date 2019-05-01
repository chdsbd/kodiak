import typing
from kodiak.github import events

# A mapping of all events to their corresponding fixtures. Any new event must
# register themselves here for testing.
MAPPING = [
    (events.CheckRunEvent, "check_run_event.json"),
    (events.CheckRunEvent, "check_run_event_pull_requests.json"),
    (events.Ping, "ping_event.json"),
    (events.PullRequestEvent, "pull_request_event.json"),
    (events.PullRequestReviewEvent, "pull_request_review_event.json"),
    (events.StatusEvent, "status_event.json"),
    (events.PushEvent, "push_event.json"),
]
