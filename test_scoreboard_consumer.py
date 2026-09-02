import sys
import time
import types
import unittest

fake_rgbmatrix = types.ModuleType("rgbmatrix")

class DummyRGBMatrixOptions:
    pass

class DummyRGBMatrix:
    def __init__(self, *args, **kwargs):
        pass

fake_rgbmatrix.RGBMatrixOptions = DummyRGBMatrixOptions
fake_rgbmatrix.RGBMatrix = DummyRGBMatrix
fake_rgbmatrix.graphics = types.SimpleNamespace()

sys.modules.setdefault("rgbmatrix", fake_rgbmatrix)

from scoreboard_consumer import EventDisplay, detect_runner_advance_animation, draw_base_diamond


class FakeCanvas:
    def __init__(self):
        self.pixels = []

    def SetPixel(self, x, y, r, g, b):
        self.pixels.append((x, y, r, g, b))


class EventDisplayGameFilterTests(unittest.TestCase):
    def test_ignores_events_for_other_games(self):
        display = EventDisplay(render_timeout=5, render_frequency=0)

        other_game = {
            "game_pk": "999",
            "currentPlay": {
                "event": "HIT_BY_PITCH",
                "about": {"inning": 7, "halfInning": "BOT", "atBatIndex": 1},
            },
        }

        selected_game = {
            "game_pk": "123",
            "currentPlay": {
                "event": "FIELD_OUT",
                "about": {"inning": 9, "halfInning": "TOP", "atBatIndex": 5},
            },
        }

        self.assertIsNone(display.update(other_game, selected_game_pk="123"))
        self.assertEqual(display.update(selected_game, selected_game_pk="123"), "FIELD OUT")

    def test_detects_runner_advance_animation(self):
        animation = detect_runner_advance_animation(
            (False, True, False),
            (False, False, True),
        )
        self.assertIsNotNone(animation)
        self.assertEqual(animation["from"], "second")
        self.assertEqual(animation["to"], "third")

    def test_keeps_active_animation_alive_across_ticks(self):
        previous = (True, False, False)
        current = (False, True, False)

        animation = detect_runner_advance_animation(previous, current)
        self.assertIsNotNone(animation)
        self.assertEqual(animation["from"], "first")
        self.assertEqual(animation["to"], "second")

        active = animation
        self.assertIsNotNone(active)
        self.assertGreaterEqual(active["duration"], 0.5)

    def test_runner_flash_coords_match_diamond_path(self):
        canvas = FakeCanvas()
        draw_base_diamond(
            canvas,
            26,
            0,
            on_first=True,
            on_second=False,
            on_third=False,
            advance_animation={
                "from": "first",
                "to": "second",
                "start": time.time(),
                "flash_interval": 0.12,
                "repeat_count": 3,
                "duration": 0.9,
            },
        )

        coords = {(x, y) for x, y, *_ in canvas.pixels}
        expected = {(33, 1), (34, 2), (35, 3)}
        self.assertTrue(expected.issubset(coords))


if __name__ == "__main__":
    unittest.main()
