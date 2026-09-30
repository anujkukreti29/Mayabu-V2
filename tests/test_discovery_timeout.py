from mayabu.jobs.worker import discovery_task_timeout_seconds


def test_discovery_timeout_grows_with_pages_and_stays_bounded():
    one = discovery_task_timeout_seconds(max_pages=1, page_timeout_ms=50_000)
    eight = discovery_task_timeout_seconds(max_pages=8, page_timeout_ms=50_000)
    assert one == 100
    assert eight == 695
    assert eight < 800
