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


class _Task:
    id: int
    id_generator = IDGenerator()

    function: Callable
    args: list
    kwargs: dict

    eta: float

    @property
    def ready(self):
        return self._current_execution is not None or self.eta == 0

    _current_execution: "Generator | None" = None

    def execute(self) -> "tuple[bool, bool]":
        """
        Returns:
            started, completed: Indication if function execution started or/and completed on this call
        """

        # Function execution is already in progress
        if self._current_execution is not None:
            try:
                next(self._current_execution)
                return False, False  # Not started nor completed, because is in progress
            except StopIteration:
                self._current_execution = None
                return False, True  # Not started but completed

        # Function execution is not in progress, start it
        execution = self.function(*self.args, **self.kwargs)

        # Function is a generator, execution will be handled in fragments
        if hasattr(execution, "__next__"):
            self._current_execution = execution
            _, completed = self.execute()
            return True, completed  # Started and maybe completed
        else:
            return True, True  # Started and completed


class Timeout(_Task):
    def __init__(
        self,
        function: Callable,
        timeout: float,
        args: list = None,
        kwargs: dict = None,
    ):
        self.id = self.id_generator()

        self.function = function
        self.timeout = timeout
        self.args = args or []
        self.kwargs = kwargs or {}

        self.time_created = monotonic()

    @property
    def eta(self):
        return max(0, self.time_created + self.timeout - monotonic())

    def __repr__(self) -> str:
        return "Timeout(id={}, function={}, timeout={}, args={}, kwargs={})".format(
            self.id, self.function, self.eta, self.args, self.kwargs
        )


class Interval(_Task):
    def __init__(
        self,
        function: Callable,
        interval: float,
        args: list = None,
        kwargs: dict = None,
        *,
        include_execution_time: bool = True,
        execute_immediately: bool = False,
    ):
        self.id = self.id_generator()

        self.function = function
        self.interval = interval
        self.args = args or []
        self.kwargs = kwargs or {}

        self.include_execution_time = include_execution_time

        self.time_created = monotonic()
        self.time_last_executed = None if execute_immediately else self.time_created

    @property
    def eta(self):
        return max(0, (self.time_last_executed or 0) + self.interval - monotonic())

    def execute(self):
        time_before_executing = monotonic()
        started, completed = super().execute()

        if started if self.include_execution_time else completed:
            self.time_last_executed = time_before_executing

        return started, completed

    def __repr__(self) -> str:
        return "Interval(id={}, function={}, interval={}, args={}, kwargs={})".format(
            self.id, self.function, self.eta, self.args, self.kwargs
        )


class EventLoop:
    """
    Class for managing tasks and executing them after timeout or in interval.
    Allows running multiple functions in "parallel", without using threads.

    Enables pausing execution of function and resuming it at later time, after processing
    other tasks.
    """

    def __init__(self):
        self.tasks: "list[Timeout | Interval]" = []

    def add(self, *tasks: "Timeout | Interval") -> "list[int]":
        """
        Add tasks to event loop

        Args:
            tasks: Tasks to add

        Returns:
            List of ids of added tasks
        """
        # Check if all tasks are instances of Event class
        for task in tasks:
            if not isinstance(task, (Timeout, Interval)):
                raise ValueError(f"Invalid task type: {type(task)}")

        # Add tasks to loop
        self.tasks.extend(tasks)

        # Return ids of tasks
        return [task.id for task in tasks]

    def timeout(self, timeout: float, *, args: list = None, kwargs: dict = None):
        """
        Decorator for adding function to event loop as Timeout

        Args:
            timeout: Timeout in seconds
            args: Positional arguments to pass to function
            kwargs: Keyword arguments to pass to function
        """

        def decorator(function: Callable):
            self.add(Timeout(function, timeout, args, kwargs))
            return function

        return decorator

    def interval(
        self,
        interval: float,
        *,
        args: list = None,
        kwargs: dict = None,
        include_execution_time: bool = True,
        execute_immediately: bool = False,
    ):
        """
        Decorator for adding function to event loop as Interval

        Args:
            interval: Interval in seconds
            args: Positional arguments to pass to function
            kwargs: Keyword arguments to pass to function
            include_execution_time: Whether to include execution time in interval
            execute_immediately: Whether to execute function immediately
        """

        def decorator(function: Callable):
            self.add(
                Interval(
                    function,
                    interval,
                    args,
                    kwargs,
                    include_execution_time=include_execution_time,
                    execute_immediately=execute_immediately,
                )
            )
            return function

        return decorator

    def cancel(self, *task_ids: "list[int]"):
        """
        Cancel tasks and remove them from event loop
        """
        self.tasks = [task for task in self.tasks if task.id not in task_ids]

    def clear(self):
        """
        Clear all tasks from event loop
        """
        self.tasks.clear()

    def loop(self):
        """
        Execute all ready tasks and return
        """
        ready_tasks = (task for task in self.tasks if task.ready)

        for task in ready_tasks:
            _, completed = task.execute()

            if completed and isinstance(task, Timeout):
                self.tasks.remove(task)

    def loop_forever(self, delay: float = None):
        """
        Loops forever, running pending tasks and listening for dispatched events

        Args:
            delay: Delay between each loop
        """
        while True:
            try:
                self.loop()
                if delay:
                    sleep(delay)
            except KeyboardInterrupt:
                break

    def __repr__(self) -> str:
        return "EventLoop(tasks={})".format(self.tasks)
