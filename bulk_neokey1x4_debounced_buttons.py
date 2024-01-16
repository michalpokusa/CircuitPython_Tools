from lib.adafruit_neokey.neokey1x4 import NeoKey1x4

from time import monotonic


class NeoKey1x4_Debounced_Button:
    _neopixel_locked = False

    def __init__(
        self,
        bulk: "Bulk_NeoKey1x4_Debounced_Buttons",
        neokey1x4_idx: int,
        slot_idx: int,
    ) -> None:
        self.bulk = bulk
        self.neokey1x4_idx = neokey1x4_idx
        self.slot_idx = slot_idx

    def update(self):
        """Updates button state."""
        self.bulk.update()

    @property
    def clicked(self) -> bool:
        """Returns `True` if button was not pressed previously and currently is."""
        return self.bulk._clicked(self.neokey1x4_idx, self.slot_idx)

    @property
    def pressed(self) -> bool:
        """Returns `True` if button is currently pressed."""
        return self.bulk._pressed(self.neokey1x4_idx, self.slot_idx)

    @property
    def released(self) -> bool:
        """Returns `True` if button was pressed previously and currently is not."""
        return self.bulk._released(self.neokey1x4_idx, self.slot_idx)

    @property
    def consecutive_clicks(self) -> int:
        """Returns number of consecutive clicks. `0` if no clicks."""
        return self.bulk._consecutive_clicks(self.neokey1x4_idx, self.slot_idx)

    @property
    def hold_time(self) -> float:
        """Returns time in seconds that button is being held. `0` if not held."""
        return self.bulk._hold_time(self.neokey1x4_idx, self.slot_idx)

    def lock_pixel(self, color: int = None):
        """Sets the NeoPixel for this NeoKey1x4 slot to the specified color and locks it."""
        if color is not None:
            self.pixel = color
        self._neopixel_locked = True

    def unlock_pixel(self):
        """Unlocks the NeoPixel"""
        self._neopixel_locked = False

    def _get_pixel(self) -> int:
        return self.bulk.neokey1x4s[self.neokey1x4_idx].pixels[self.slot_idx]

    def _set_pixel(self, value: int) -> None:
        # Do not change the pixel color if it is locked
        if self._neopixel_locked:
            return
        self.bulk.neokey1x4s[self.neokey1x4_idx].pixels[self.slot_idx] = value

    pixel = property(_get_pixel, _set_pixel)
    """Controls the NeoPixel for this NeoKey1x4 slot."""


class Bulk_NeoKey1x4_Debounced_Buttons:
    consecutive_clicks_time_budget: float = 0.4
    """Time in seconds to wait for next consecutive click."""

    last_activity_time: float
    """Last time any button was pressed or released."""

    def __init__(self, neokey1x4s: "list[NeoKey1x4]") -> None:
        self.neokey1x4s = neokey1x4s
        self._previously_pressed = ([False] * 4,) * len(neokey1x4s)
        self._currently_pressed = ([False] * 4,) * len(neokey1x4s)
        self._buttons = None

        self.last_activity_time = monotonic()

    def update(self):
        self._previously_pressed = self._currently_pressed
        self._currently_pressed = (
            neokey1x4.get_keys() for neokey1x4 in self.neokey1x4s
        )

        if self._currently_pressed != self._previously_pressed:
            self.last_activity_time = monotonic()

    @property
    def buttons(self):
        if self._buttons is None:
            self._buttons = [
                NeoKey1x4_Debounced_Button(self, neokey1x4_idx, slot_idx)
                for neokey1x4_idx in range(len(self.neokey1x4s))
                for slot_idx in range(4)
            ]

        return self._buttons

    def _get_brightness(self):
        return self.neokey1x4s[0].pixels.brightness

    def _set_brightness(self, value: float):
        new_value = min(max(value, 0), 1)

        for neokey1x4 in self.neokey1x4s:
            if neokey1x4.pixels.brightness == new_value:
                continue

            neokey1x4.pixels.brightness = new_value

    brightness = property(_get_brightness, _set_brightness)

    def _set_pixels(self, value: "int | list[int]"):
        for neokey1x4 in self.neokey1x4s:
            neokey1x4.pixels.fill(value)

    pixels = property(None, _set_pixels)

    def _clicked(self, neokey1x4_idx: int, slot_idx: int) -> bool:
        return (
            not self._previously_pressed[neokey1x4_idx][slot_idx]
            and self._currently_pressed[neokey1x4_idx][slot_idx]
        )

    def _pressed(self, neokey1x4_idx: int, slot_idx: int) -> bool:
        self.update()
        return self._currently_pressed[neokey1x4_idx][slot_idx]

    def _released(self, neokey1x4_idx: int, slot_idx: int) -> bool:
        return (
            self._previously_pressed[neokey1x4_idx][slot_idx]
            and not self._currently_pressed[neokey1x4_idx][slot_idx]
        )

    def _consecutive_clicks(self, neokey1x4_idx: int, slot_idx: int) -> int:
        if not self._clicked(neokey1x4_idx, slot_idx):
            return 0

        times_clicked = 1
        last_click_time = monotonic()

        while monotonic() < last_click_time + self.consecutive_clicks_time_budget:
            self.update()
            if not self._clicked(neokey1x4_idx, slot_idx):
                continue
            times_clicked += 1
            last_click_time = monotonic()

        return times_clicked

    def _hold_time(self, neokey1x4_idx: int, slot_idx: int) -> float:
        if not self._pressed(neokey1x4_idx, slot_idx):
            return 0

        hold_start_time = monotonic()

        while self._pressed(neokey1x4_idx, slot_idx):
            pass

        return monotonic() - hold_start_time
