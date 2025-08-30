import threading
import time


class RateLimiter:
    """Limits the rate at which one or multiple sections of code may be called.

    The limiting is thread-safe: threads that are rate-limited will sleep until they
    are not anymore.

    Important: The rate limiter only limits the start of execution of the rate-limited
    code. This means for example that for rate-limited web queries of one per second,
    it is assured that at most one request is started per second, but there may be
    multiple queries running concurrently if the first one takes time to execute.
    """

    def __init__(self, reqs_per_interval: int, interval_sec: float):
        """Create the rate limiter with the specified rate

        :param reqs_per_interval: Number of requests that can be done per interval.
            Must be strictly positive
        :param interval_sec: The interval in seconds. Must be strictly positive
        """

        if reqs_per_interval <= 0.0:
            raise ValueError("reqs_per_interval can't be less than 0")
        if interval_sec <= 0:
            raise ValueError("interval_sec can't be less than 0")

        # Configuration variables
        self.reqs_per_interval = reqs_per_interval
        self.interval_sec = interval_sec

        # Current state
        self.lock = threading.Lock()
        self.last_call = 0.0
        self.remaining_requests = None

    def _update_remaining(self):
        """Update the number of remaining requests that can be done and the time of
        last call
        """
        if self.remaining_requests is None:
            # On first invocation, we have the number of requests available
            self.remaining_requests = float(self.reqs_per_interval)

        else:
            # On following invocations, increase the number of requests available
            # based on the time since last invocation
            since_last_call = time.time() - self.last_call
            self.remaining_requests += since_last_call * (
                self.reqs_per_interval / self.interval_sec
            )
            # Number of requests cannot exceed the max number per interval
            self.remaining_requests = min(
                self.remaining_requests, float(self.reqs_per_interval)
            )

        self.last_call = time.time()

    def __enter__(self):
        with self.lock:
            self._update_remaining()

            # Assert to avoid typing errors
            assert self.remaining_requests is not None

            # Delay if necessary
            while self.remaining_requests < 0.999:
                time.sleep(
                    (1.0 - self.remaining_requests)
                    * (self.interval_sec / self.reqs_per_interval)
                )
                self._update_remaining()

            # "Pay" for the execution of the rate limited code section
            self.remaining_requests -= 1.0

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # Nothing to do: limiting is only done on the start of execution of the
        # rate-limited code
        pass
