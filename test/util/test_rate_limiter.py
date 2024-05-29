import time
from concurrent.futures import ThreadPoolExecutor

from beets.util.rate_limiter import RateLimiter

# 10 reqs per 0.1 second
REQS_PER_INTERVAL = 10
INTERVAL_SEC = 0.1

# Expected time to wait to be able to do one more request after being rate limited
WAIT_FOR_ONE_REQ = INTERVAL_SEC / REQS_PER_INTERVAL


def run_and_collect_delta_start_times(num_reqs: int) -> list[float]:
    """Launch requests through the rate limiter and collect the durations between the
    time before the first request and the starting time of each request.

    :param num_reqs: Number of requests to run
    :return: A list of delta start times in seconds: non rate-limited ones should be
        close to 0
    """
    rate_limiter = RateLimiter(REQS_PER_INTERVAL, INTERVAL_SEC)

    delta_start_times = []

    start = time.time()
    for _ in range(num_reqs):
        with rate_limiter:
            delta_start_times.append(time.time() - start)

    return delta_start_times


def test_all_reqs_in_one_interval():
    delta_start_times = run_and_collect_delta_start_times(REQS_PER_INTERVAL)

    for i in range(10):
        assert delta_start_times[i] < WAIT_FOR_ONE_REQ, (
            f"request {i} should not have been rate-limited"
        )


def test_more_reqs_in_one_interval():
    delta_start_times = run_and_collect_delta_start_times(2 * REQS_PER_INTERVAL)

    # 20 reqs with rate-limitation of 10 reqs per 0.1s
    # -> 10 reqs immediately, then 10*(1 req per 0.1s)

    for i in range(10):
        assert delta_start_times[i] < WAIT_FOR_ONE_REQ, (
            f"request {i} should not have been rate-limited"
        )

    for i in range(10, len(delta_start_times)):
        # Non rate-limited reqs are at interval 0
        # 1st rate-limited req is at interval 1
        # 2nd rate-limited req is at interval 2
        # etc.
        expected_interval = i - 9
        expected_start_time = expected_interval * WAIT_FOR_ONE_REQ

        assert delta_start_times[i] >= expected_start_time, (
            f"request {i} has executed sooner than it should have"
        )
        # Do not test that the request has executed before 'expected_time + dt'
        # because thread may sleep for more time than requested and cause tests
        # instabilities


def test_reuse_after_no_requests():
    rate_limiter = RateLimiter(REQS_PER_INTERVAL, INTERVAL_SEC)

    # Use up all requests
    start = time.time()
    for _ in range(REQS_PER_INTERVAL):
        with rate_limiter:
            pass
    end = time.time()
    assert (end - start) < WAIT_FOR_ONE_REQ, (
        "requests should not have been rate-limited"
    )

    # Do no request for half an interval
    time.sleep(INTERVAL_SEC / 2)

    # Now, we should be able to do half the REQS_PER_INTERVAL with no rate limitation
    start = time.time()
    for _ in range(REQS_PER_INTERVAL // 2):
        with rate_limiter:
            pass
    end = time.time()
    assert (end - start) < WAIT_FOR_ONE_REQ, (
        "requests should not have been rate-limited"
    )


def test_rate_limit_multithread():
    rate_limiter = RateLimiter(REQS_PER_INTERVAL, INTERVAL_SEC)

    # 50 requests (== 50 threads)
    nb_requests = 50
    # Each thread sleeps for 0.5 second
    thread_sleep_duration = 5 * INTERVAL_SEC

    # We have 50 requests for a rate limiter or 10 reqs per 0.1s
    # -> 10 reqs immediately, then 10*(1 req per 0.1s)
    # -> Each req takes time, but rate limiter should only care about the start of a
    #    request, not how long it takes

    def worker_task(nth_thread):
        t0 = time.time()
        with rate_limiter:
            # Check the start time
            start = time.time() - t0
            if nth_thread <= 10:
                # They should start immediately
                assert start < WAIT_FOR_ONE_REQ, (
                    f"request {nth_thread} should not have been rate-limited"
                )
            else:
                # Non rate-limited reqs are at interval 0
                # 1st rate-limited req is at interval 1
                # 2nd rate-limited req is at interval 2
                # etc.
                expected_interval = nth_thread - 9
                expected_start_time = expected_interval * WAIT_FOR_ONE_REQ

                assert start >= expected_start_time, (
                    f"request {nth_thread} has executed sooner than it should have"
                )
                # Do not test that the request has executed before 'expected_time + dt'
                # because thread may sleep for more time than requested and cause tests
                # instabilities

            # Sleep for a while to block the thread -> We do that to check that
            # the rate limiter is not affected by the duration of the request
            time.sleep(thread_sleep_duration)

    # Use a thread pool executor so that threre is no time difference between the start
    # of execution between threads (due to thread creation time), making harder to
    # compare times.
    # By using a thread pool, all threads are created at once.
    with ThreadPoolExecutor(nb_requests) as executor:
        for nth_thread in range(nb_requests):
            executor.submit(worker_task, nth_thread)
