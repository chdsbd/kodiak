from kodiak.github import events

# A mapping of all events to their corresponding fixtures. Any new event must
# register themselves here for testing.
MAPPING = [
    ("check_run", events.CheckRunEvent, "check_run_event.json"),
    ("check_run", events.CheckRunEvent, "check_run_event_pull_requests.json"),
    ("pull_request", events.PullRequestEvent, "pull_request_event.json"),
    (
        "pull_request_review",
        events.PullRequestReviewEvent,
        "pull_request_review_event.json",
    ),
    ("status", events.StatusEvent, "status_event.json"),
    ("push", events.PushEvent, "push_event.json"),
]
