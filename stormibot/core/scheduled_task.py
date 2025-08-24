import time
from random import randint

class ScheduledTask:
    def __init__(self, interval_func, action, immediate=False):
        """
        interval_func: function returning interval in seconds (e.g. lambda: randint(30, 45))
        action: function to execute
        immediate: if True, the task runs on the first loop iteration
        """
        self.interval_func = interval_func
        self.action = action
        self.last_run = 0 if immediate else time.time()
        self.next_interval = self.interval_func()

    def maybe_run(self, now):
        """Run the task if enough time has passed."""
        if now - self.last_run >= self.next_interval:
            self.action()
            self.last_run = now
            self.next_interval = self.interval_func()