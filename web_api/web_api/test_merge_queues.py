from web_api.merge_queues import QueueInfo, queue_info_from_name


def test_queue_info_from_name() -> None:
    assert queue_info_from_name("merge_queue:11256551.sbdchd/squawk/main") == QueueInfo(
        "sbdchd", "squawk", "main"
    )
    assert queue_info_from_name(
        "merge_queue:11256551.sbdchd/squawk/main.test.foo"
    ) == QueueInfo("sbdchd", "squawk", "main.test.foo")
    assert queue_info_from_name(
        "merge_queue:11256551.sbdchd/squawk/chris/main.test.foo"
    ) == QueueInfo("sbdchd", "squawk", "chris/main.test.foo")
