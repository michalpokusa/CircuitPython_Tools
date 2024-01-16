try:
    from typing import Callable
except ImportError:
    pass

from time import monotonic

import digitalio
from microcontroller import Pin


class _IDebouncedButton:
    """
    Base class for debounced buttons.

    #### This class is not meant to be used directly, it is meant to be subclassed.
    """

    _previously_pressed: bool = False
    _currently_pressed: bool = False

    consecutive_clicks_time_budget: float = 0.5
    """Time in seconds to wait for next consecutive click."""

    def __init__(self) -> None:
        raise NotImplementedError

    def _update(self) -> None:
        self._previously_pressed = self._currently_pressed
        self._currently_pressed = self.pressed

    @property
    def clicked(self) -> bool:
        """Returns `True` if button was not pressed previously and currently is."""
        self._update()
        return not self._previously_pressed and self._currently_pressed

    @property
    def pressed(self) -> bool:
        """
        Returns `True` if button is currently pressed.

        #### This method needs to be overridden in subclasses
        as it is not implemented in the base class. All other methods use this it one way or another.
        """
        raise NotImplementedError

    @property
    def released(self) -> bool:
        """Returns `True` if button was pressed previously and currently is not."""
        self._update()
        return self._previously_pressed and not self._currently_pressed

    @property
    def consecutive_clicks(self) -> int:
        """Returns number of consecutive clicks. `0` if no clicks."""
        if not self.clicked:
            return 0

        times_clicked = 1
        last_click_time = monotonic()

        while monotonic() < last_click_time + self.consecutive_clicks_time_budget:
            if not self.clicked:
                continue
            times_clicked += 1
            last_click_time = monotonic()

        return times_clicked

    @property
    def hold_time(self) -> float:
        """Returns time in seconds that button is being held. `0` if not held."""
        if not self.pressed:
            return 0

        hold_start_time = monotonic()

        while self.pressed:
            pass

        return monotonic() - hold_start_time

    def _wait_for_condition(self, condition: Callable, timeout: float = None) -> bool:
        start_time = monotonic()
        while not condition():
            if timeout is not None and start_time + timeout < monotonic():
                return False
        return True

    def wait_for_click(self, *, timeout: float = None) -> bool:
        """
        Waits for click for maximum of `timeout` seconds.

        Returns:
            bool: `True` if hold was detected, `False` otherwise.
        """
        return self._wait_for_condition(lambda: self.clicked, timeout)

    def wait_for_press(self, *, timeout: float = None) -> bool:
        """
        Waits for press for maximum of `timeout` seconds.

        Returns:
            bool: `True` if hold was detected, `False` otherwise.
        """
        return self._wait_for_condition(lambda: self.pressed, timeout)

    def wait_for_release(self, *, timeout: float = None) -> bool:
        """
        Waits for release for maximum of `timeout` seconds.

        Returns:
            bool: `True` if hold was detected, `False` otherwise.
        """
        return self._wait_for_condition(lambda: self.released, timeout)

    def wait_for_consecutive_clicks(
        self, clicks: int, *, timeout: float = None
    ) -> None:
        """
        Waits for specified number of consecutive `clicks` for maximum of `timeout` seconds.

        Returns:
            bool: `True` if hold was detected, `False` otherwise.
        """
        return self._wait_for_condition(
            lambda: self.consecutive_clicks == clicks, timeout
        )

    def wait_for_hold(
        self, min_time: float = None, max_time: float = None, timeout: float = None
    ) -> None:
        """
        Waits for hold between `min_time` and `max_time` for maximum of `timeout` seconds.

        Returns:
            bool: `True` if hold was detected, `False` otherwise.
        """
        min_time, max_time = min_time or 0, max_time or 1000000
        return self._wait_for_condition(
            lambda: min_time < self.hold_time < max_time, timeout
        )


class Pin_DOWN_Debounced_Button(_IDebouncedButton):
    def __init__(self, button_pin: Pin) -> None:
        self._button_pin = digitalio.DigitalInOut(button_pin)
        self._button_pin.switch_to_input(pull=digitalio.Pull.DOWN)

    @property
    def pressed(self) -> bool:
        return self._button_pin.value


class Pin_UP_Debounced_Button(_IDebouncedButton):
    def __init__(self, button_pin: Pin) -> None:
        self._button_pin = digitalio.DigitalInOut(button_pin)
        self._button_pin.switch_to_input(pull=digitalio.Pull.UP)

    @property
    def pressed(self) -> bool:
        return not self._button_pin.value
