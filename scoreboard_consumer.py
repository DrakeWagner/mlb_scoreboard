import json
import time
from confluent_kafka import Consumer
from resources.fonts import FONT_5X8, FONT_4X6
from resources.teams import TEAM_ABBREV
from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics


def read_config():
    config = {}
    with open("client.properties") as fh:
        for line in fh:
            line = line.strip()
            if len(line) != 0 and line[0] != "#":
                try:
                    parameter, value = line.split('=', 1)
                    config[parameter.strip()] = value.strip()
                except ValueError:
                    continue
    return config


def setup_matrix():
    options = RGBMatrixOptions()
    options.rows = 32
    options.cols = 64
    options.chain_length = 1
    options.parallel = 1
    options.hardware_mapping = 'adafruit-hat'
    options.gpio_slowdown = 4
    options.brightness = 60
    return RGBMatrix(options=options)


def set_pixel(canvas, x, y, r, g, b):
    if 0 <= x < 64 and 0 <= y < 32:
        canvas.SetPixel(x, y, r, g, b)


def draw_char(canvas, x, y, ch, font, char_w, char_h, r, g, b):
    bmp = font.get(ch)
    if not bmp:
        return char_w + 1
    for row in range(char_h):
        for col in range(char_w):
            if bmp[row][col]:
                set_pixel(canvas, x + col, y + row, r, g, b)
    return char_w + 1


def draw_text_5x8(canvas, x, y, text, r, g, b):
    cx = x
    for ch in str(text).upper():
        cx += draw_char(canvas, cx, y, ch, FONT_5X8, 5, 8, r, g, b)


def draw_text_4x6(canvas, x, y, text, r, g, b):
    cx = x
    for ch in str(text).upper():
        cx += draw_char(canvas, cx, y, ch, FONT_4X6, 4, 6, r, g, b)


def draw_count_dots(canvas, x, y, count, max_dots, lit_r, lit_g, lit_b):
    for i in range(max_dots):
        lit = i < count
        px = x + i * 5
        rr, gg, bb = (lit_r, lit_g, lit_b) if lit else (30, 20, 10)
        for dx in range(2):
            for dy in range(2):
                set_pixel(canvas, px + dx, y + dy, rr, gg, bb)


def draw_base_diamond(canvas, x, y, on_first, on_second, on_third):
    occupied = (255, 120, 0)
    empty = (40, 30, 10)
    line = (20, 15, 5)

    def draw_base(bx, by, lit):
        c = occupied if lit else empty
        for dx in range(2):    
            for dy in range(2):
                set_pixel(canvas, bx + dx, by + dy, *c)

    draw_base(x + 5, y,     on_second)
    draw_base(x + 9, y + 4, on_first)
    draw_base(x + 1, y + 4, on_third)
    draw_base(x + 5, y + 8, False)

    # diamond lines
    for i in range(1, 5):
        set_pixel(canvas, x + 5 - i, y + i,     *line)
        set_pixel(canvas, x + 6 + i, y + i,     *line)
        set_pixel(canvas, x + 5 - i, y + 9 - i, *line)
        set_pixel(canvas, x + 6 + i, y + 9 - i, *line)


def draw_arrow(canvas, x, y, is_top):
    color = (255, 220, 0)
    if is_top:
        set_pixel(canvas, x + 2, y + 1, *color)
        for i in (1, 2, 3): set_pixel(canvas, x + i, y + 2, *color)
        for i in range(5):  set_pixel(canvas, x + i, y + 3, *color)
    else:
        for i in range(5):  set_pixel(canvas, x + i, y + 1, *color)
        for i in (1, 2, 3): set_pixel(canvas, x + i, y + 2, *color)
        set_pixel(canvas, x + 2, y + 3, *color)


def render(canvas, game_data):
    canvas.Clear()

    away = TEAM_ABBREV.get(game_data.get('away_team', ''), 'AWY')
    home = TEAM_ABBREV.get(game_data.get('home_team', ''), 'HME')
    away_s = game_data.get('away_score', 0)
    home_s = game_data.get('home_score', 0)
    inning = game_data.get('current_inning') or 1
    balls = game_data.get('balls') or 0
    strikes = game_data.get('strikes') or 0
    outs = game_data.get('outs') or 0
    on_first  = bool(game_data.get('runner_on_first'))
    on_second = bool(game_data.get('runner_on_second'))
    on_third  = bool(game_data.get('runner_on_third'))

    # reset strikes and balls on out
    global previous_outs
    if 'previous_outs' not in globals():
        previous_outs = outs

    if outs >= 3 or outs > previous_outs:
        balls = 0
        strikes = 0

    # reset baserunners at end of inning
    if outs >= 3:
        on_first = on_second = on_third = False

    previous_outs = outs

    raw_half = (game_data.get('inning_half') or '').strip().upper()
    is_top = raw_half in ('TOP', 'T')

    away_color = (100, 220, 100) if away_s > home_s else (180, 180, 180)
    home_color = (100, 220, 100) if home_s > away_s else (180, 180, 180)

    # LEFT ZONE - Centered
    away_width = len(away) * 6 - 1
    draw_text_5x8(canvas, 10 - away_width//2, 0, away, 220, 220, 220)
    draw_text_5x8(canvas, 10 - (len(str(away_s))*6)//2, 9, away_s, *away_color)

    # BALLS
    draw_char(canvas, 1,  22, 'B', FONT_4X6, 4, 6, 160, 160, 160)
    draw_char(canvas, 6,  22, 'A', FONT_4X6, 4, 6, 160, 160, 160)
    draw_char(canvas, 11, 22, 'L', FONT_4X6, 4, 6, 160, 160, 160)
    draw_char(canvas, 15, 22, 'L', FONT_4X6, 4, 6, 160, 160, 160)
    draw_count_dots(canvas, 4, 29, balls, 3, 255, 150, 0)

    # MID ZONE
    draw_base_diamond(canvas, 26, 0, on_first, on_second, on_third)

    # Inning
    inn_num = str(inning)
    num_w = len(inn_num) * 5 - 1
    arrow_w = 5
    total_w = arrow_w + 2 + num_w
    inn_x = 20 + (24 - total_w) // 2
    inn_y = 11
    draw_arrow(canvas, inn_x, inn_y, is_top)
    draw_text_4x6(canvas, inn_x + arrow_w + 2, inn_y, inn_num, 255, 220, 0)

    draw_text_4x6(canvas, 23, 22, 'STRK', 160, 160, 160)
    draw_count_dots(canvas, 29, 29, strikes, 2, 255, 80, 80)

    # RIGHT ZONE - Centered
    home_width = len(home) * 6 - 1
    draw_text_5x8(canvas, 54 - home_width//2, 0, home, 220, 220, 220)
    draw_text_5x8(canvas, 54 - (len(str(home_s))*6)//2, 9, home_s, *home_color)

    # OUT with narrower T
    draw_text_4x6(canvas, 48, 22, 'OU', 160, 160, 160)
    t_x = 58
    set_pixel(canvas, t_x,   22, 160,160,160)
    set_pixel(canvas, t_x+1, 22, 160,160,160)
    set_pixel(canvas, t_x+2, 22, 160,160,160)
    for i in range(4):
        set_pixel(canvas, t_x+1, 23 + i, 160,160,160)

    draw_count_dots(canvas, 50, 29, outs, 3, 255, 80, 80)


def main():
    config = read_config()
    config['log_level'] = '0'
    config['group.id'] = 'scoreboard-consumer'
    config['auto.offset.reset'] = 'latest'

    consumer = Consumer(config)
    consumer.subscribe(['mlb_game_state'])

    matrix = setup_matrix()
    canvas = matrix.CreateFrameCanvas()

    print("Scoreboard consumer started...")

    latest = {}

    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is not None and not msg.error():
                value = json.loads(msg.value().decode('utf-8'))
                latest[value.get('game_pk')] = value

            if latest:
                game_data = latest[next(iter(latest))]
                render(canvas, game_data)
                canvas = matrix.SwapOnVSync(canvas)

    except KeyboardInterrupt:
        print("\nShutting down.")
        consumer.close()


if __name__ == "__main__":
    main()