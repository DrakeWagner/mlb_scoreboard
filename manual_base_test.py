#!/usr/bin/env python3
import argparse
import time

import scoreboard_consumer as sc


class SimCanvas:
    def __init__(self):
        self.pixels = set()

    def Clear(self):
        self.pixels.clear()

    def SetPixel(self, x, y, r, g, b):
        if 0 <= x < 64 and 0 <= y < 32:
            self.pixels.add((x, y))


def render_ascii(state, animation=None):
    canvas = SimCanvas()
    sc.draw_base_diamond(
        canvas,
        26,
        0,
        on_first=state[0],
        on_second=state[1],
        on_third=state[2],
        advance_animation=animation,
    )

    rows = []
    for y in range(0, 11):
        row = []
        for x in range(0, 42):
            row.append("█" if (x, y) in canvas.pixels else " ")
        rows.append("".join(row).rstrip())

    print("\n".join(rows))


def render_matrix(canvas, state, animation=None):
    canvas.Clear()

    sc.draw_base_diamond(
        canvas,
        26,
        0,
        on_first=state[0],
        on_second=state[1],
        on_third=state[2],
        advance_animation=animation,
    )

    sc.draw_text_4x6(canvas, 1, 22, 'BASE', 160, 160, 160)
    sc.draw_text_4x6(canvas, 23, 22, 'TEST', 160, 160, 160)


def main():
    parser = argparse.ArgumentParser(description="Manual baserunner debug harness for the RGB matrix")
    parser.add_argument("--sim", action="store_true", help="Use the terminal simulation instead of the real RGB matrix")
    parser.add_argument(
        "--transition",
        choices=[
            "home-home",
            "home-first",
            "home-second",
            "home-third",
            "first-second",
            "first-third",
            "first-home",
            "second-third",
            "second-home",
            "third-home",
            "reset",
        ],
        help="Single-run transition test. Use no flags to enter the interactive menu loop.",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Optional number of seconds to show the selected transition before exiting.",
    )
    args = parser.parse_args()

    print("Manual base-running debug harness")
    print("This lets you force base states and test the runner animation on the same drawing code as the board.\n")

    transition_map = {
        "home-home": ((False, False, False), (False, False, False)),
        "home-first": ((False, False, False), (True, False, False)),
        "home-second": ((False, False, False), (False, True, False)),
        "home-third": ((False, False, False), (False, False, True)),
        "first-second": ((True, False, False), (False, True, False)),
        "first-third": ((True, False, False), (False, False, True)),
        "first-home": ((True, False, False), (False, False, False)),
        "second-third": ((False, True, False), (False, False, True)),
        "second-home": ((False, True, False), (False, False, False)),
        "third-home": ((False, False, True), (False, False, False)),
        "reset": ((False, False, False), (False, False, False)),
    }

    def run_transition(target_name, sim_mode, duration_seconds=None):
        previous, target = transition_map[target_name]
        movement = [{"start": "home", "end": "home"}] if target_name == "home-home" else None
        animation = sc.detect_runner_advance_animation(previous, target, movement)
        print(f"\nTransition: {target_name} :: {previous} -> {target}")
        if animation:
            print(f"Animation: {animation['from']} -> {animation['to']} | duration={animation['duration']}")

        if not animation:
            print("No runner advance animation detected for this transition.")
            return

        animation["start"] = time.time()
        if duration_seconds is None:
            duration_seconds = animation.get("duration", 3.0)
        stop_time = time.time() + duration_seconds

        if sim_mode:
            while time.time() < stop_time:
                render_ascii(target, animation=animation)
                time.sleep(animation.get("flash_interval", 0.2))
            return

        matrix = sc.setup_matrix()
        canvas = matrix.CreateFrameCanvas()
        while time.time() < stop_time:
            render_matrix(canvas, target, animation=animation)
            canvas = matrix.SwapOnVSync(canvas)
            time.sleep(0.1)

    def print_menu():
        print("\nInteractive transition menu")
        print("1) home-home")
        print("2) home-first")
        print("3) home-second")
        print("4) home-third")
        print("5) first-second")
        print("6) first-third")
        print("7) first-home")
        print("8) second-third")
        print("9) second-home")
        print("0) third-home")
        print("A) toggle first")
        print("B) toggle second")
        print("C) toggle third")
        print("D) clear bases")
        print("q) exit")

    current_state = [False, False, False]

    if args.transition:
        print(f"\nPreselected transition: {args.transition}")
        run_transition(args.transition, args.sim, args.duration)
        if args.duration is not None:
            print("Exiting after selected duration.")
            return

    while True:
        print_menu()
        try:
            choice = input("\nSelect transition test: ").strip()
        except EOFError:
            return

        if choice.lower() == "q":
            print("Exiting manual runner tester.")
            return

        mapping = {
            "1": "home-home",
            "2": "home-first",
            "3": "home-second",
            "4": "home-third",
            "5": "first-second",
            "6": "first-third",
            "7": "first-home",
            "8": "second-third",
            "9": "second-home",
            "0": "third-home",
        }

        target_name = mapping.get(choice)
        if target_name is not None:
            run_transition(target_name, args.sim)
            continue

        quick_state = {
            "a": "toggle_first",
            "b": "toggle_second",
            "c": "toggle_third",
            "d": "clear",
        }
        action = quick_state.get(choice.lower())
        if action is None:
            print("Invalid selection. Choose a number from 0-9, A-D, or q.")
            continue

        if action == "toggle_first":
            current_state[0] = not current_state[0]
        elif action == "toggle_second":
            current_state[1] = not current_state[1]
        elif action == "toggle_third":
            current_state[2] = not current_state[2]
        elif action == "clear":
            current_state = [False, False, False]

        state = current_state[:]
        print(f"\nQuick base state: {tuple(state)}")
        if args.sim:
            render_ascii(state)
        else:
            matrix = sc.setup_matrix()
            canvas = matrix.CreateFrameCanvas()
            render_matrix(canvas, state)
            canvas = matrix.SwapOnVSync(canvas)
            time.sleep(1.5)


if __name__ == "__main__":
    main()
