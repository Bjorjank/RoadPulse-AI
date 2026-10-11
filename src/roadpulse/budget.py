"""Conservative cooperative pacing; this is not an OS CPU quota."""
import time


def rest_after(work_seconds, cancelled, *, clock=time.monotonic, sleep=time.sleep):
    """Rest four times the active frame time; remain cancellable during rest."""
    deadline = clock() + max(0.0, work_seconds) * 4.0
    while True:
        if cancelled():
            return False
        remaining = deadline - clock()
        if remaining <= 0:
            return True
        sleep(min(0.25, remaining))
