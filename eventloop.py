try:
    from typing import Callable, Generator
except ImportError:
    pass

from sys import exit as sys_exit
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

    tags: "list[str]"
    interval: "float | None"
    delay: "float | None"
    timeout: "float | None"

    event_loop: "EventLoop | None" = None
    _current_call: "Generator | None" = None

    @staticmethod
    def _interval_function(function: "Callable", interval: float):
        def intervaled_function(*args, **kwargs):
            while True:
                function(*args, **kwargs)

                yield from sync_delay(seconds=interval)

        return intervaled_function

    @staticmethod
    def _delay_function(function: "Callable", delay: float):
        def delayed_function(*args, **kwargs):
            yield from sync_delay(seconds=delay)
            function(*args, **kwargs)

        return delayed_function

    def __init__(
        self,
        function: "Callable",
        args: list = None,
        kwargs: dict = None,
        *,
        tags: "list[str]" = None,
        interval: float = None,
        delay: float = None,
        timeout: float = None,
        bind: bool = False,
    ) -> None:
        self.id = self._id_generator()

        self.function = function
        self.args = args or []
        self.kwargs = kwargs or {}

        self.tags = tags or []
        self.interval = interval
        self.delay = delay

        if interval:
            self.function = self._interval_function(self.function, interval)

        if delay:
            self.function = self._delay_function(self.function, delay)

        self.timeout = timeout
        self.bind = bind

        self.time_created = monotonic()
        self.time_started = None
        self.time_completed = None

        self.started = False
        self.completed = False
        self.timed_out = False
        self.errored = False

    def progress(self):
        """
        Calls a `function` with given `args` and `kwargs`, pauses on yields if `function`
        is a generator
        """

        # Function call is already in progress
        if self._current_call is not None:
            # Timed out
            if self.timeout and self.time_started + self.timeout < monotonic():
                self._current_call = None
                self.completed = True
                self.time_completed = monotonic()
                self.timed_out = True
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
                    self.errored = True
                    raise error

        # Function call is not in progress, start it
        self.started = True
        self.time_started = monotonic()

        call = (
            self.function(self, *self.args, **self.kwargs)
            if self.bind
            else self.function(*self.args, **self.kwargs)
        )

        # Function is a generator, call will be handled in fragments
        if hasattr(call, "__next__"):
            self._current_call = call
            self.call()
        # Function is not a generator, call is completed
        else:
            self._current_call = None
            self.completed = True
            self.time_completed = monotonic()

    @property
    def completed_successfully(self) -> bool:
        """
        Returns whether the task has been completed successfully, without errors or timeouts
        """
        return self.completed and not self.errored and not self.timed_out

    @property
    def elapsed_time(self) -> float:
        if not self.started:
            return 0

        if self.completed:
            return self.time_completed - self.time_started

        return monotonic() - self.time_started

    def __eq__(self, value: "Task") -> bool:
        if not isinstance(value, Task):
            raise ValueError(f"Cannot compare {type(self)} with {type(value)}")

        return (
            self.time_created == value.time_created  # Has same creation time
            and self.id == value.id  # Has same id
        )

    def __gt__(self, other: "Task"):
        if not isinstance(other, Task):
            raise ValueError(f"Cannot compare {type(self)} with {type(other)}")

        return (
            self.time_created < other.time_created  # Has been created earlier
            or self.id < other.id  # Has lower id, so it was instantiated earlier
        )

    def __lt__(self, other: "Task"):
        return not self.__gt__(other)

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} "
            + f"id={self.id}"
            + f", tags={self.tags}"
            + f", interval={self.interval}"
            + f", delay={self.delay}"
            + f", timeout={self.timeout}"
            + f", bind={self.bind}"
            + f", args={self.args}"
            + f", kwargs={self.kwargs}"
            + ">"
        )


def sync_delay(
    *, hours: float = 0, minutes: float = 0, seconds: float = 0, miliseconds: int = 0
):
    """
    Allows to simulate a `time.sleep` or `asyncio.sleep` call in a generator function,
    without blocking the loop.

    Always pauses for at least the given time, but may pause for longer if other tasks are
    running in the meantime.

    Examples:
    ```
        yield from sync_delay(minutes=1.5)
        yield from sync_delay(hours=1, minutes=30, seconds=45)
    ```
    """
    total_seconds = (hours * 3600) + (minutes * 60) + seconds + (miliseconds / 1000)
    unlock_time = monotonic() + total_seconds

    should_yield_at_least_once = True

    while monotonic() < unlock_time:
        yield
        should_yield_at_least_once = False

    if should_yield_at_least_once:
        yield


class async_delay:
    """
    Allows to simulate a `time.sleep` or `asyncio.sleep` call in a generator function,
    without blocking the loop.

    Pauses for the minimum time required to retain the interval between calls.

    Examples:
    ```
        delay = async_delay(hours=1, minutes=30, seconds=45)

        yield from delay
    ```
    """

    def __init__(
        self,
        *,
        hours: float = 0,
        minutes: float = 0,
        seconds: float = 0,
        miliseconds: int = 0,
    ):
        self._total_seconds = (
            (hours * 3600) + (minutes * 60) + seconds + (miliseconds / 1000)
        )
        self._unlock_time = monotonic() + self._total_seconds

        self._should_yield_at_least_once = True

    def __iter__(self):
        while monotonic() < self._unlock_time:
            yield
            self._should_yield_at_least_once = False

        if self._should_yield_at_least_once:
            yield

        missed_unlocks = (monotonic() - self._unlock_time) // self._total_seconds
        self._unlock_time += self._total_seconds * (missed_unlocks + 1)


class EventLoop:
    """
    Class for managing tasks and calling them after timeout or in interval.
    Allows running multiple functions in "parallel", without using threads.

    Enables pausing function call and resuming it at later time, after processing
    other tasks.
    """

    def __init__(self):
        self.tasks: "list[Task]" = []

    def add(self, *tasks: "Task") -> "list[Task]":
        for task in tasks:
            task.event_loop = self

        self.tasks.extend(tasks)

        return tasks

    def cancel(
        self,
        *tasks: "Task",
        ids: "list[int]" = None,
        tags: "list[str | list[str]]" = None,
    ):
        """
        Cancel tasks and remove them from event loop
        """

        # Explicit tasks
        if tasks:
            self.tasks = [task for task in self.tasks if task not in tasks]

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

    def loop(self, *, sort_before_calling: bool = False):
        """
        Call all pending tasks and return

        Args:
            sort_before_calling: Whether to sort tasks before calling them
        """
        self.tasks = [task for task in self.tasks if not task.completed]

        if sort_before_calling:
            self.tasks.sort(reverse=True)

        for task in self.tasks:
            task.progress()

    def loop_forever(
        self,
        *,
        time_between_loops: float = None,
        raise_errors: bool = True,
        sys_exit_after: bool = True,
        stop_when_no_tasks: bool = False,
    ):
        """
        Loops forever, running pending tasks and scheduling new ones

        Args:
            time_between_loops: Time between each loop
            raise_errors: Whether to raise errors or not
            sys_exit_after: Exits program after loop ends
            stop_when_no_tasks: Stop loop when there are no tasks left
        """
        while self.tasks or not stop_when_no_tasks:
            try:
                self.loop()
                if time_between_loops:
                    sleep(time_between_loops)
            except KeyboardInterrupt:
                break
            except Exception as error:
                if raise_errors:
                    raise error
                else:
                    print_exception(error)

        if sys_exit_after:
            sys_exit()

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} tasks={self.tasks}>"


class DebugEventLoop(EventLoop):
    def _print_loops_per_second(self):
        print(f"Loops per second: {self.loops_per_second}")
        self.reset_loops_per_second()

    def __init__(self):
        super().__init__()

        self.counted_loops = 0
        self.time_started_counting = monotonic()

        self.add(Task(self._print_loops_per_second, interval=5))

    def loop(self, *, sort_before_calling: bool = False):
        super().loop(sort_before_calling=sort_before_calling)

        self.counted_loops += 1

    @property
    def loops_per_second(self) -> float:
        """
        Returns average number of loops per second
        """
        return self.counted_loops / (monotonic() - self.time_started_counting)

    def reset_loops_per_second(self):
        """
        Resets loops per second counter
        """
        self.counted_loops = 0
        self.time_started_counting = monotonic()
