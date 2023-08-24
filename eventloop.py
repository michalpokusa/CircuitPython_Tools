try:
    from typing import Callable, Generator
except ImportError:
    pass

from time import monotonic, sleep


class IDGenerator:
    id = 0

    def __call__(self) -> int:
        self.id += 1
        return self.id


class Task:
    _id_generator = IDGenerator()
    id: int

    function: Callable
    args: list
    kwargs: dict

    priority: int

    event_loop: "EventLoop | None" = None
    _current_call: "Generator | None" = None

    def __init__(
        self,
        function: Callable,
        args: list = None,
        kwargs: dict = None,
        *,
        priority: int = 0,
    ) -> None:
        self.id = self._id_generator()

        self.function = function
        self.args = args or []
        self.kwargs = kwargs or {}

        self.priority = priority

        self.time_created = monotonic()
        self.time_started = None
        self.time_completed = None

        self.started = False
        self.completed = False

    def call(self):
        """
        Calls a `function` with given `args` and `kwargs`, pauses on first yield if `function`
        is a generator
        """

        # Function call is already in progress
        if self._current_call is not None:
            try:
                # In progess, continue until next yield
                next(self._current_call)
            except StopIteration:
                # Completed
                self._current_call = None
                self.completed = True
                self.time_completed = monotonic()
            finally:
                return

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

    def __repr__(self) -> str:
        return "Task(id={}, priority={}, function={}, args={}, kwargs={}, time_created={})".format(
            self.id,
            self.priority,
            self.function,
            self.args,
            self.kwargs,
            self.time_created,
        )


class _Schedule:
    _id_generator = IDGenerator()
    id: int

    eta: "float | None"
    ready: bool

    def __init__(
        self,
        function: Callable,
        args: list = None,
        kwargs: dict = None,
        priority: int = 0,
    ):
        self.id = _Schedule._id_generator()

        self.function = function
        self.args = args or []
        self.kwargs = kwargs or {}
        self.priority = priority

        self.time_created = monotonic()

    @property
    def task(self) -> Task:
        return Task(self.function, self.args, self.kwargs, priority=self.priority)


class Timeout(_Schedule):
    def __init__(
        self,
        function: Callable,
        timeout: float,
        args: list = None,
        kwargs: dict = None,
        priority: int = 0,
    ):
        super().__init__(function, args, kwargs, priority=priority)
        self.timeout = timeout

    @property
    def eta(self):
        return max(0, self.time_created + self.timeout - monotonic())

    @property
    def ready(self):
        return self.eta == 0

    def __repr__(self) -> str:
        return "Timeout(id={}, eta={}, timeout={}, function={}, args={}, kwargs={})".format(
            self.id, self.eta, self.timeout, self.function, self.args, self.kwargs
        )


class Interval(_Schedule):
    def __init__(
        self,
        function: Callable,
        interval: float,
        args: list = None,
        kwargs: dict = None,
        priority: int = 0,
        *,
        blocking: bool = False,
        immediate: bool = False,
    ):
        super().__init__(function, args, kwargs, priority=priority)

        self.interval = interval
        self.blocking = blocking
        self._blocking_task: "Task | None" = None
        self.time_last_called = None if immediate else self.time_created

    @property
    def eta(self):
        return max(0, (self.time_last_called or 0) + self.interval - monotonic())

    @property
    def ready(self):
        if self.blocking and self._blocking_task:
            if not self._blocking_task.completed:
                return False
            self.time_last_called = self._blocking_task.time_completed
            self._blocking_task = None

        return self.eta == 0

    @property
    def task(self) -> Task:
        self.time_last_called = monotonic()
        _task = super().task
        if self.blocking:
            self._blocking_task = _task
        return _task

    def __repr__(self) -> str:
        return "Interval(id={}, eta={}, interval={}, function={}, args={}, kwargs={})".format(
            self.id, self.eta, self.interval, self.function, self.args, self.kwargs
        )


class Countdown(_Schedule):
    class State:
        WAITING = "waiting"
        PAUSED = "paused"
        COMPLETED = "completed"

    def __init__(
        self,
        function: Callable,
        timer: float,
        args: list = None,
        kwargs: dict = None,
        priority: int = 0,
    ):
        super().__init__(function, args, kwargs, priority=priority)

        self._initial_timer = timer
        self._time_to_run_at = monotonic() + timer
        self.state = self.State.WAITING

        self.resume()

    @property
    def eta(self):
        if not self.state == self.State.WAITING:
            return None
        return max(0, self._time_to_run_at - monotonic())

    @property
    def ready(self):
        if not self.state == self.State.WAITING:
            return False
        return self.eta == 0

    def pause(self):
        """
        Pause timer
        """
        if not self.state == self.State.WAITING:
            return

        self.state = self.State.PAUSED

        self._timer = self._time_to_run_at - monotonic()
        self._time_to_run_at = None

    def resume(self):
        """
        Resume timer from paused state
        """
        if not self.state == self.State.PAUSED:
            return

        self.state = self.State.WAITING

        self._time_to_run_at = monotonic() + self._timer
        self._timer = None

    def reset(self):
        """
        Reset timer to initial value and pause
        """
        self.state = self.State.PAUSED

        self._timer = self._initial_timer
        self._time_to_run_at = None

    def restart(self):
        """
        Restart timer from initial value and start
        """
        self.reset()
        self.resume()

    @property
    def task(self) -> Task:
        self.state = self.State.COMPLETED
        self._time_to_run_at = None
        return super().task

    def __repr__(self) -> str:
        return "Countdown(id={}, eta={}, state={}, function={}, args={}, kwargs={})".format(
            self.id, self.eta, self.state, self.function, self.args, self.kwargs
        )


class EventLoop:
    """
    Class for managing tasks and calling them after timeout or in interval.
    Allows running multiple functions in "parallel", without using threads.

    Enables pausing function call and resuming it at later time, after processing
    other tasks.
    """

    def __init__(self):
        self.tasks: "list[Task]" = []
        self.schedules: "list[_Schedule]" = []

    def timeout(
        self,
        timeout: float,
        *,
        args: list = None,
        kwargs: dict = None,
        priority: int = 0,
    ):
        """
        Decorator for adding function to event loop as timeout

        Args:
            timeout: Timeout in seconds
            args: Positional arguments to pass to function
            kwargs: Keyword arguments to pass to function
            priority: Priority of task
        """

        def decorator(function: Callable):
            self.schedules.append(Timeout(function, timeout, args, kwargs, priority))
            return function

        return decorator

    def interval(
        self,
        interval: float,
        *,
        args: list = None,
        kwargs: dict = None,
        priority: int = 0,
        blocking: bool = True,
        immediate: bool = False,
    ):
        """
        Decorator for adding function to event loop as interval

        Args:
            interval: Interval in seconds
            args: Positional arguments to pass to function
            kwargs: Keyword arguments to pass to function
            priority: Priority of task
            blocking: Whether to include call time in interval
            immediate: Whether to call function immediately
        """

        def decorator(function: Callable):
            self.schedules.append(
                Interval(
                    function,
                    interval,
                    args,
                    kwargs,
                    priority=priority,
                    blocking=blocking,
                    immediate=immediate,
                )
            )
            return function

        return decorator

    def _schedule_tasks(self):
        for schedule in self.schedules:
            if schedule.ready:
                task = schedule.task
                task.event_loop = self

                self.tasks.append(task)

                if isinstance(schedule, Timeout):
                    self.schedules.remove(schedule)

    def cancel(self, *task_ids: "list[int]"):
        """
        Cancel tasks and remove them from event loop
        """
        self.tasks = [task for task in self.tasks if task.id not in task_ids]

    def loop(self, limit: int = None):
        """
        Call all pending tasks and return

        Args:
            limit: Number of tasks to run before returning
        """
        self._schedule_tasks()
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

    def __repr__(self) -> str:
        return "EventLoop(tasks={}, schedules={})".format(self.tasks, self.schedules)
