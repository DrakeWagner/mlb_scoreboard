import sys
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

from scoreboard_consumer import EventDisplay, detect_runner_advance_animation


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


if __name__ == "__main__":
    unittest.main()
