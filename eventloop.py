try:
    from typing import Callable, Generator
except ImportError:
    pass

from time import monotonic, sleep
from traceback import print_exception


class IDGenerator:
    id = 0

    def __call__(self) -> int:
        self.id += 1
        return self.id


class Task:
    """
    Class for managing function calls and their priority.
    """

    _id_generator = IDGenerator()
    id: int

    function: "Callable"
    args: list
    kwargs: dict

    priority: int
    tags: "list[str]"
    delay: "float | None"
    timeout: "float | None"
    interval: "float | None"

    event_loop: "EventLoop | None" = None
    _current_call: "Generator | None" = None

    @staticmethod
    def _interval_function(function: "Callable", interval: float):
        def intervaled_function(*args, **kwargs):
            while True:
                function(*args, **kwargs)

                yield from sync_delay(seconds=interval)

        return intervaled_function

    def __init__(
        self,
        function: "Callable",
        args: list = None,
        kwargs: dict = None,
        *,
        priority: int = 0,
        tags: "list[str]" = None,
        delay: float = None,
        timeout: float = None,
        interval: float = None,
    ) -> None:
        self.id = self._id_generator()

        self.function = function
        self.args = args or []
        self.kwargs = kwargs or {}

        self.priority = priority
        self.tags = tags or []
        self.delay = delay
        self.timeout = timeout
        self.interval = interval

        if interval:
            self.function = self._interval_function(self.function, interval)

        self.time_created = monotonic()
        self.time_started = None
        self.time_completed = None

        self.started = False
        self.completed = False

    def call(self):
        """
        Calls a `function` with given `args` and `kwargs`, pauses on yields if `function`
        is a generator
        """

        # Function call is delayed
        if self.delay and not self.started:
            if monotonic() < self.time_created + self.delay:
                return

        # Function call is already in progress
        if self._current_call is not None:
            # Timed out
            if self.timeout and self.time_started + self.timeout < monotonic():
                self._current_call = None
                self.completed = True
                self.time_completed = monotonic()
                return

            try:
                # In progess, continue until next yield
                next(self._current_call)
                return
            except Exception as error:
                # Completed or error
                self._current_call = None
                self.completed = True
                self.time_completed = monotonic()

                if isinstance(error, StopIteration):
                    return
                else:
                    raise error

        # Function call is not in progress, start it
        self.started = True
        self.time_started = monotonic()
        call = self.function(*self.args, **self.kwargs)

        # Function is a generator, call will be handled in fragments
        if hasattr(call, "__next__"):
            self._current_call = call
            self.call()
        # Function is not a generator, call is completed
        else:
            self._current_call = None
            self.completed = True
            self.time_completed = monotonic()

    def __eq__(self, value: "Task") -> bool:
        if not isinstance(value, Task):
            raise ValueError(f"Cannot compare {type(self)} with {type(value)}")

        return (
            self.priority == value.priority and self.time_created == value.time_created
        )

    def __gt__(self, other: "Task"):
        if not isinstance(other, Task):
            raise ValueError(f"Cannot compare {type(self)} with {type(other)}")

        if self.priority == other.priority:
            return self.time_created < other.time_created

        return other.priority < self.priority

    def __lt__(self, other: "Task"):
        return not self.__gt__(other)

    def __repr__(self) -> str:
        return (
            "Task("
            f"id={self.id}, "
            f"priority={self.priority}, "
            f"function={self.function}, "
            f"args={self.args}, "
            f"kwargs={self.kwargs}, "
            f"time_created={self.time_created}, "
            f"tags={self.tags}"
            ")"
        )


def delay(
    *, hours: float = 0, minutes: float = 0, seconds: float, miliseconds: int = 0
):
    """
    Allows to simulate a `time.sleep` or `asyncio.sleep` call in a generator function,
    without blocking the loop.

    Examples:
    ```
        # Wait for 1.5s
        yield from delay(seconds=1, miliseconds=500)
        yield from delay(seconds=1.5)

        # Wait for 1m30s
        yield from delay(seconds=90)
        yield from delay(minutes=1, seconds=30)
        yield from delay(minutes=1.5)

        # Wait for 1h30m45s
        yield from delay(hours=1, minutes=30, seconds=45)
        yield from delay(minutes=90, seconds=45)
        yield from delay(minutes=90.75)
    ```
    """
    total_seconds = (hours * 3600) + (minutes * 60) + seconds + (miliseconds / 1000)
    unlock_time = monotonic() + total_seconds
    while monotonic() < unlock_time:
        yield


class EventLoop:
    """
    Class for managing tasks and calling them after timeout or in interval.
    Allows running multiple functions in "parallel", without using threads.

    Enables pausing function call and resuming it at later time, after processing
    other tasks.
    """

    def __init__(self):
        self.tasks: "list[Task]" = []

    def add(
        self,
        *tasks: "Task",
    ) -> "list[Task]":
        for task in tasks:
            task.event_loop = self

        self.tasks.extend(tasks)

        return tasks

    def cancel(self, ids: "list[int]" = None, tags: "list[str | list[str]]" = None):
        """
        Cancel tasks and remove them from event loop
        """

        # Based on ids
        if ids:
            self.tasks = [task for task in self.tasks if task.id not in ids]

        # Based on tags
        if tags:
            for tag_group in tags:
                tag_group = (
                    {tag_group} if isinstance(tag_group, str) else set(tag_group)
                )

                self.tasks = [
                    task
                    for task in self.tasks
                    if not tag_group.issubset(set(task.tags))
                ]

    def loop(self, limit: int = None):
        """
        Call all pending tasks and return

        Args:
            limit: Number of tasks to run before returning
        """
        self.tasks.sort(reverse=True)

        for task in self.tasks[:limit]:
            task.call()

        self.tasks = [task for task in self.tasks if not task.completed]

    def loop_forever(
        self, limit: int = None, delay: float = None, raise_errors: bool = True
    ):
        """
        Loops forever, running pending tasks and scheduling new ones

        Args:
            limit: Number of tasks to run in each loop between scheduling new ones
            delay: Delay between each loop
            raise_errors: Whether to raise errors or not
        """
        while True:
            try:
                self.loop(limit)
                if delay:
                    sleep(delay)
            except KeyboardInterrupt:
                break
            except Exception as error:
                if raise_errors:
                    raise error
                else:
                    print_exception(error)

    def __repr__(self) -> str:
        return f"EventLoop(tasks={self.tasks})"
