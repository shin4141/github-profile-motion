"""Deterministic, script-free README GIFs; never writes to GitHub's graph."""
import argparse
from datetime import date, datetime, timedelta, timezone
import json
import math
from pathlib import Path
import random
import subprocess
from PIL import Image, ImageColor, ImageDraw, ImageFont

ROOT = Path(__file__).parent
W, H = 846, 148
COLS, ROWS, WINDOW_DAYS = 53, 7, 365
STEP, TILE, X0, Y0 = 15, 11, 34, 32
CENTER = (TILE + 1) // 2
HEADING = "Technical Boundary Audit & Repair for AI Systems"
FRAME_MS = 80
WALK_SPEED = 17
EDGE_MARGIN = 31  # entire awake sprite and its shadow clear the right edge
STRIDE = (W + 2*EDGE_MARGIN) / 24  # gait phase completes 24 cycles around a wrap
B_PAUSE_FRAMES = 5
THEMES = {
    "light": {"background": (255, 255, 255), "empty": (239, 242, 245),
              "shadow": (173, 187, 177)},
    "dark": {"background": (13, 17, 23), "empty": (21, 27, 35),
             "shadow": (48, 67, 54)},
}
LEVEL_INDEX = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2,
               "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}


def font(size, bold=False):
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default(size=size)


def color(hex_value):
    rgb = ImageColor.getrgb(hex_value)
    if len(rgb) != 3:
        raise ValueError("Use opaque #RRGGBB colors")
    return rgb


def blend(a, b, ratio):
    return tuple(round(x * (1-ratio) + y * ratio) for x, y in zip(a, b))


def capture(username, output, start, end):
    """Optional one-time public contribution snapshot through authenticated gh."""
    if not username or not username.strip():
        raise ValueError("GitHub username must not be empty")
    start_date, end_date = date.fromisoformat(start), date.fromisoformat(end)
    if start_date > end_date:
        raise ValueError("--from-date must be on or before --to-date")
    query = ("query { user(login: " + json.dumps(username) + ") { "
             "contributionsCollection(from: " + json.dumps(start + "T00:00:00Z") + ", to: "
             + json.dumps(end + "T23:59:59Z") + ") { contributionCalendar { weeks { "
             "contributionDays { date contributionCount contributionLevel } } } } } }")
    result = subprocess.run(["gh", "api", "graphql", "-f", "query=" + query],
                            check=True, capture_output=True, text=True)
    response = json.loads(result.stdout)
    if response.get("errors"):
        raise ValueError("GitHub GraphQL error: " + str(response["errors"]))
    user = response.get("data", {}).get("user")
    if user is None:
        raise ValueError("GitHub user not found or not accessible: " + username)
    weeks = user["contributionsCollection"]["contributionCalendar"]["weeks"]
    days = [dict(date=day["date"], count=day["contributionCount"],
                 level=day["contributionLevel"])
            for week in weeks for day in week["contributionDays"]]
    payload = {"username": username, "source": "GitHub GraphQL contributionsCollection snapshot",
               "observed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "days": days}
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def sample(username, output):
    """Explicitly synthetic activity for testing customization, never real data."""
    from datetime import date, timedelta
    start = date(2025, 9, 21)
    days = [dict(date=(start+timedelta(days=i)).isoformat(),
                 count=(i*7 % 13 if i % 4 else 0)) for i in range(WINDOW_DAYS)]
    payload = {"username": username, "source": "SYNTHETIC example, not a GitHub contribution claim",
               "observed_at": "synthetic", "days": days}
    output.write_text(json.dumps(payload, indent=2) + "\n")


def activity_grid(data):
    entries = {d["date"]: d["count"] for d in data["days"]}
    if len(entries) != len(data["days"]) or any(type(v) is not int or v < 0 for v in entries.values()):
        raise ValueError("Activity dates must be unique, with nonnegative integer counts")
    dates = sorted(entries)
    if len(dates) != WINDOW_DAYS:
        raise ValueError("A full year needs 365 dated activity entries")
    end = date.fromisoformat(dates[-1])
    start = end - timedelta(days=WINDOW_DAYS-1)
    if dates != [(start + timedelta(days=i)).isoformat() for i in range(WINDOW_DAYS)]:
        raise ValueError("Activity dates must cover each of the last 365 days without gaps")
    first = start - timedelta(days=(start.weekday()+1) % 7)
    # None means a calendar padding day, never an invented zero contribution.
    return [[entries.get((first + timedelta(weeks=col, days=row)).isoformat())
             for row in range(ROWS)] for col in range(COLS)]


def activity_levels(data):
    days = data["days"]
    present = ["level" in day for day in days]
    if not any(present):
        return None  # synthetic or user-supplied snapshots retain count-based color.
    if not all(present):
        raise ValueError("Contribution levels must be present for every dated day")
    for day in days:
        level = day["level"]
        if not isinstance(level, str) or level not in LEVEL_INDEX or (day["count"] == 0) != (level == "NONE"):
            raise ValueError("Invalid GitHub contribution level for dated count")
    entries = {day["date"]: day["level"] for day in days}
    first_date = date.fromisoformat(min(entries))
    first = first_date - timedelta(days=(first_date.weekday()+1) % 7)
    return [[entries.get((first + timedelta(weeks=col, days=row)).isoformat())
             for row in range(ROWS)] for col in range(COLS)]


def draw_calendar_labels(im, data, theme):
    draw = ImageDraw.Draw(im)
    first_date = date.fromisoformat(min(day["date"] for day in data["days"]))
    first = first_date - timedelta(days=(first_date.weekday()+1) % 7)
    muted = (87, 96, 106) if theme == "light" else (139, 148, 158)
    previous_month = None
    for col in range(COLS):
        week = first + timedelta(weeks=col)
        month = (week.year, week.month)
        if month != previous_month:
            draw.text((X0 + col*STEP, 8), week.strftime("%b"),
                      fill=muted, font=font(11))
            previous_month = month
    for row, label in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        draw.text((4, Y0 + row*STEP), label, fill=muted, font=font(10))


def base_frame(data, accent, theme):
    bg = THEMES[theme]["background"]
    im = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(im)
    grid = activity_grid(data)
    levels = activity_levels(data)
    draw_calendar_labels(im, data, theme)
    for col in range(COLS):
        for row in range(ROWS):
            n = grid[col][row]
            if n is None:
                continue
            x, y = X0 + col*STEP, Y0 + row*STEP
            d.rounded_rectangle((x, y, x+TILE, y+TILE), radius=2,
                                fill=square_color(n, accent, theme,
                                                  levels[col][row] if levels else None))
    return im, grid


def target_points(grid, seed):
    active = [(c, r) for c in range(4, COLS-4) for r in range(1, 6)
              if (grid[c][r] or 0) > 0]
    if not active:
        active = [(19, 3), (38, 4)]
    rng = random.Random(seed)
    first = rng.choice(active[:max(1, len(active)//2)])
    second = rng.choice(active[max(1, len(active)//2):] or active)
    return [first, second]


def position(target, t):
    # Two visits: approach, touch/glow, pause; common motion for any icon.
    anchors = [(0, (19, 3)), (13, target[0]), (20, target[0]),
               (31, target[0]), (45, target[1]), (53, target[1]), (65, target[1])]
    for (f0, p0), (f1, p1) in zip(anchors, anchors[1:]):
        if t <= f1:
            s = (t-f0)/(f1-f0)
            s = s*s*(3-2*s)
            return (p0[0]*(1-s)+p1[0]*s, p0[1]*(1-s)+p1[1]*s)
    return target[1]


def touch_frames(config, data, seed, asset_root=ROOT, theme="light"):
    accent, glow = palette_colors(config, theme)
    base, grid = base_frame(data, accent, theme)
    targets = target_points(grid, seed)
    icon = Image.open(asset_root / config["icon"]).convert("RGBA")
    icon.thumbnail((51, 51), Image.Resampling.LANCZOS)
    for t in range(66):
        im = base.copy()
        d = ImageDraw.Draw(im, "RGBA")
        for visit, (start, end) in enumerate(((17, 27), (50, 60))):
            if start <= t <= end:
                c, r = targets[visit]
                x, y = X0 + c*STEP+CENTER, Y0 + r*STEP+CENTER
                power = max(0, 1-abs(t-(start+end)/2)/((end-start)/2))
                d.ellipse((x-14, y-14, x+14, y+14), fill=(*glow, int(35*power)))
                d.rounded_rectangle((x-6, y-6, x+6, y+6), radius=3,
                                    fill=(*glow, int(125*power)))
        col, row = position(targets, t)
        walking = t < 16 or 31 < t < 49
        hop = abs(math.sin(t*math.pi/5))*7 if walking else 0
        # During touch, the icon leans toward the cell. During pause, it rests.
        tilt = -9 if 17 <= t <= 25 or 50 <= t <= 58 else (3*math.sin(t*.7) if walking else 0)
        sprite = icon.rotate(tilt, Image.Resampling.BICUBIC, expand=True)
        x = int(X0 + col*STEP - sprite.width/2)
        y = int(Y0 + row*STEP - sprite.height - 1 - hop)
        im.paste(sprite, (x, y), sprite)
        yield im


def smoothstep(value):
    value = max(0.0, min(1.0, value))
    return value * value * (3 - 2 * value)


def scene_stops(grid, seed):
    """Choose separate left-of-center and right-side squares at one gait height."""
    ranges = (range(18, 24), range(35, 41))
    stops = []
    for scene, columns in enumerate(ranges):
        active = [(col, 3) for col in columns if (grid[col][3] or 0) > 0]
        stops.append(random.Random(f"{seed}:stop:{scene}").choice(
            active or [(list(columns)[len(columns)//2], 3)]))
    return stops


def shock_plan(grid, seed, stop, levels=None):
    """One fixed per-cell motion plan: radial launch, irregular voluntary return."""
    cx, cy = X0 + stop[0]*STEP + CENTER, Y0 + stop[1]*STEP - 17
    plan = []
    for col in range(COLS):
        for row in range(ROWS):
            if grid[col][row] is None:
                continue
            x, y = X0 + col*STEP, Y0 + row*STEP
            rng = random.Random(f"{seed}:{col}:{row}")
            dx, dy = x+CENTER-cx, y+CENTER-cy
            dist = math.hypot(dx, dy)
            if dist < 3:
                angle = rng.random()*math.tau
                dx, dy, dist = math.cos(angle), math.sin(angle), 1
            reach = 36 + min(52, dist*.27) + rng.uniform(-6, 8)
            # Slight tangent adds a natural tumble without reversing the burst.
            tangent = rng.uniform(-9, 9)
            ox = dx/dist*reach - dy/dist*tangent
            oy = dy/dist*reach + dx/dist*tangent
            # The tighter, frameless canvas keeps every launched tile in view.
            # A small reserve also covers the subpixel return hesitation.
            ox = max(7-x, min(W-TILE-7-x, ox))
            oy = max(7-y, min(H-TILE-7-y, oy))
            launch = 27 + min(8, int(dist/35))
            return_start = 46 + rng.randrange(0, 17)
            return_duration = 12 + rng.randrange(0, 14)
            plan.append(dict(col=col, row=row, count=grid[col][row],
                             level=levels[col][row] if levels else None, x=x, y=y,
                             ox=ox, oy=oy, launch=launch,
                             return_start=return_start,
                             return_end=return_start+return_duration,
                             phase=rng.random()*math.tau))
    return plan


def cell_position(cell, t):
    """Decorative position only; a cell's original count/color is immutable."""
    if t < cell["launch"] or t >= cell["return_end"]:
        return cell["x"], cell["y"]
    if t < cell["launch"]+7:
        p = (t-cell["launch"])/7
        amount = 1-(1-p)**3  # quick outward impulse
        wiggle = 0
    elif t < cell["return_start"]:
        amount = 1
        wiggle = 0
    else:
        p = (t-cell["return_start"])/(cell["return_end"]-cell["return_start"])
        amount = 1-smoothstep(p)
        # Small sideways hesitation while drifting home; vanishes at both ends.
        wiggle = math.sin(p*math.tau*1.5+cell["phase"])*3.2*p*(1-p)
    return (cell["x"] + cell["ox"]*amount + wiggle,
            cell["y"] + cell["oy"]*amount - wiggle)


def shock_background(theme):
    return Image.new("RGB", (W, H), THEMES[theme]["background"])


def palette_colors(config, theme):
    if theme not in THEMES:
        raise ValueError("theme must be light or dark")
    return (color(config.get("accent_" + theme, config["accent"])),
            color(config.get("glow_" + theme, config["glow"])))


def square_color(count, accent, theme, level=None):
    empty = THEMES[theme]["empty"]
    if theme == "light":
        shades = [empty, blend(empty, accent, .35),
                  blend(empty, accent, .59), blend(empty, accent, .82),
                  blend(accent, (15, 35, 25), .26)]
        if accent == (45, 164, 78):
            shades = [empty, (172, 238, 187), (74, 194, 107),
                      (45, 164, 78), (17, 99, 41)]
    else:
        shades = [empty, blend(empty, accent, .28),
                  blend(empty, accent, .52), blend(empty, accent, .76), accent]
        if accent == (86, 211, 100):
            shades = [empty, (3, 58, 22), (25, 108, 46),
                      (46, 160, 67), (86, 211, 100)]
    index = (LEVEL_INDEX[level] if level is not None else
             0 if count == 0 else 1 if count < 3 else 2 if count < 6 else
             3 if count < 10 else 4)
    return shades[index]


def load_icon(path, asset_root=ROOT):
    icon = Image.open(asset_root / path).convert("RGBA")
    icon.thumbnail((64, 64), Image.Resampling.LANCZOS)
    return icon


def creature_at(frame, icon, x, ground_y, angle=0, scale=1, lift=0):
    size = (max(1, min(icon.width, round(min(icon.width, 58)*scale))),
            max(1, min(icon.height, round(min(icon.height, 58)*scale))))
    sprite = icon if size == icon.size else icon.resize(size, Image.Resampling.LANCZOS)
    if angle:
        sprite = sprite.rotate(angle, Image.Resampling.BICUBIC, expand=True)
    frame.paste(sprite, (round(x-sprite.width/2), round(ground_y-sprite.height+12-lift)), sprite)


def walk_phase(x):
    """The same speed, scale, ground height and gait on both wrap boundaries."""
    return math.tau * (x+EDGE_MARGIN) / STRIDE


def enter_positions(stop_x):
    x = -EDGE_MARGIN
    while x < stop_x:
        x = min(stop_x, x+WALK_SPEED)
        yield x


def exit_positions(stop_x):
    x = stop_x
    while x < W+EDGE_MARGIN:
        x = min(W+EDGE_MARGIN, x+WALK_SPEED)
        yield x


def build_timeline(grid, seed):
    """A and B are states on one clock, not two GIFs glued together."""
    states = []
    stops = scene_stops(grid, seed)
    for scene, stop in enumerate(stops):
        stop_x = X0+stop[0]*STEP+CENTER
        for x in enter_positions(stop_x):
            states.append(dict(scene=scene, stage="enter", x=x, stop=stop))
        for _ in range(3):
            states.append(dict(scene=scene, stage="stop", x=stop_x, stop=stop))
        for motion_t in range(27, 88):
            states.append(dict(scene=scene, stage="event", x=stop_x,
                               stop=stop, motion_t=motion_t, pause_step=0))
            if scene == 1 and motion_t == 62:
                for pause_step in range(1, B_PAUSE_FRAMES+1):
                    states.append(dict(scene=scene, stage="event", x=stop_x,
                                       stop=stop, motion_t=motion_t,
                                       pause_step=pause_step))
        for wake_step in range(7):
            states.append(dict(scene=scene, stage="wake", x=stop_x,
                               stop=stop, wake_step=wake_step))
        for x in exit_positions(stop_x):
            states.append(dict(scene=scene, stage="exit", x=x, stop=stop))
    return states


def draw_creature(im, state, awake, sleeping, waking, specialized_sleep, theme):
    x = state["x"]
    ground_y = Y0+3*STEP+CENTER
    d = ImageDraw.Draw(im)
    d.ellipse((round(x-17), ground_y+8, round(x+17), ground_y+12),
              fill=THEMES[theme]["shadow"])
    stage = state["stage"]
    if stage in ("enter", "exit"):
        phase = walk_phase(x)
        # The little up/down step is position-based, so it never restarts at A/B.
        creature_at(im, awake, x, ground_y,
                    angle=2.5*math.sin(phase),
                    lift=2.5*(1-math.cos(phase)))
    elif stage == "stop":
        creature_at(im, awake, x, ground_y)
    elif stage == "wake":
        p = smoothstep(state["wake_step"]/6)
        if specialized_sleep:
            creature_at(im, waking, x, ground_y, angle=-10*(1-p), scale=.95+.05*p)
        else:
            creature_at(im, awake, x, ground_y, angle=-65*(1-p), scale=.84+.16*p)
    else:
        t = state["motion_t"]
        if t < 42:
            creature_at(im, awake, x, ground_y)
        elif t < 46:
            p = smoothstep((t-42)/4)
            if specialized_sleep:
                creature_at(im, sleeping, x, ground_y, angle=-10*(1-p), scale=.96)
            else:
                creature_at(im, awake, x, ground_y, angle=-65*p, scale=1-.16*p)
        else:
            breath = 1+.025*math.sin((t-46)*.6)
            pause_step = state["pause_step"]
            # Only B: one tiny stir freezes the moving squares for five frames.
            stir = (0, -1, -2, 0, 1, 0)[pause_step]
            creature_at(im, sleeping, x, ground_y,
                        angle=(0 if specialized_sleep else -65)+stir*4,
                        scale=(breath if specialized_sleep else .84*breath),
                        lift=abs(stir))


def shock_frames(config, data, seed, asset_root=ROOT, theme="light"):
    """One two-scene timeline: right exit, invisible wrap, left re-entry."""
    accent, glow = palette_colors(config, theme)
    grid = activity_grid(data)
    levels = activity_levels(data)
    states = build_timeline(grid, seed)
    plans = [shock_plan(grid, seed+scene*100003, stop, levels)
             for scene, stop in enumerate(scene_stops(grid, seed))]
    background = shock_background(theme)
    draw_calendar_labels(background, data, theme)
    awake = load_icon(config["icon"], asset_root)
    sleeping = load_icon(config["sleep_icon"], asset_root) if config.get("sleep_icon") else awake
    waking = load_icon(config["wake_icon"], asset_root) if config.get("wake_icon") else awake
    for state in states:
        im = background.copy()
        draw = ImageDraw.Draw(im)
        stop_x = X0+state["stop"][0]*STEP+CENTER
        center_y = Y0+3*STEP+CENTER-23
        t = state.get("motion_t", 0)
        plan = plans[state["scene"]]
        for cell in plan:
            x, y = cell_position(cell, t)
            x, y = round(x), round(y)
            draw.rounded_rectangle((x, y, x+TILE, y+TILE), radius=2,
                                   fill=square_color(cell["count"], accent, theme,
                                                     cell["level"]))

        # Same background and rendering on both scenes; only the shock center moves.
        for onset in (27, 31):
            age = t-onset
            if 0 <= age <= 15:
                radius_x = min(stop_x-5, W-stop_x-5, 100, 5+age*9)
                radius_y = min(center_y-(Y0-5), H-center_y-5, 5+age*3)
                strength = (1-age/16)*.75
                ring = blend(THEMES[theme]["background"], glow, strength)
                draw.ellipse((stop_x-radius_x, center_y-radius_y,
                              stop_x+radius_x, center_y+radius_y),
                             outline=ring, width=3 if age < 9 else 2)
        draw_creature(im, state, awake, sleeping, waking,
                      bool(config.get("sleep_icon")), theme)
        yield im


def frames(config, data, seed, pattern="shock", asset_root=ROOT, theme="light"):
    if pattern == "shock":
        return shock_frames(config, data, seed, asset_root, theme)
    if pattern == "touch":
        return touch_frames(config, data, seed, asset_root, theme)
    raise ValueError("pattern must be shock or touch")


def heading_frames(mobile=False):
    w, h = (440, 86) if mobile else (850, 62)
    bg = (17, 23, 37)
    purple, cyan = (151, 107, 226), (79, 220, 230)
    title_font = font(22 if mobile else 29, True)
    for t in range(40):
        im = Image.new("RGB", (w, h), bg)
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((1, 1, w-2, h-2), radius=12, outline=(61, 69, 92), width=1)
        for x in range(20, w-20, 3):
            phase = (x/w - t/40) % 1
            lum = math.exp(-((phase-.45)/.17)**2)
            c = blend(purple, cyan, x/w)
            c = blend(bg, c, .22 + .65*lum)
            d.line((x, h-8, x+3, h-8), fill=c, width=3)
        if mobile:
            d.text((19, 10), "Technical Boundary Audit", fill=(238, 243, 252), font=title_font)
            d.text((19, 41), "& Repair for AI Systems", fill=(238, 243, 252), font=title_font)
        else:
            d.text((25, 10), HEADING, fill=(238, 243, 252), font=title_font)
        yield im


def gif(images, dest, duration):
    # One global fixed palette suppresses per-frame palette flicker.
    images = list(images)
    samples = [images[0], images[len(images)//3], images[len(images)//2]]
    sheet = Image.new("RGB", (images[0].width, images[0].height*len(samples)))
    for i, sample in enumerate(samples):
        sheet.paste(sample, (0, i*sample.height))
    palette = sheet.quantize(colors=128)
    # Error diffusion from an entering icon can otherwise alter identical
    # background squares all the way across a seam in the encoded GIF.
    frames_p = [im.quantize(palette=palette, dither=Image.Dither.NONE)
                for im in images]
    frames_p[0].save(dest, save_all=True, append_images=frames_p[1:], duration=duration,
                     loop=0, disposal=2, optimize=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="JSON with username, icon, accent, glow")
    parser.add_argument("--activity", type=Path, help="Frozen dated JSON activity input")
    parser.add_argument("--seed", type=int, default=216)
    parser.add_argument("--pattern", choices=("shock", "touch"), default="shock",
                        help="Main shock/sleep loop, or retained touch/glow variant")
    parser.add_argument("--theme", choices=("light", "dark"), default="light",
                        help="Match the GitHub README light or dark appearance")
    parser.add_argument("--out", type=Path, help="Output activity GIF")
    parser.add_argument("--heading-out", type=Path, help="Output heading GIF")
    parser.add_argument("--heading-mobile-out", type=Path, help="Output two-line narrow-screen heading GIF")
    parser.add_argument("--capture", type=Path, help="Capture dated GraphQL snapshot to path, then stop")
    parser.add_argument("--username", help="Username for --capture")
    parser.add_argument("--sample", type=Path, help="Write synthetic activity for --username, then stop")
    parser.add_argument("--from-date", help="Snapshot start, YYYY-MM-DD (default: 364 days before today, UTC)")
    parser.add_argument("--to-date", help="Snapshot end, YYYY-MM-DD (default: today, UTC)")
    args = parser.parse_args()
    if args.capture:
        if not args.username:
            parser.error("--capture needs --username")
        today = datetime.now(timezone.utc).date()
        capture(args.username, args.capture,
                args.from_date or (today-timedelta(days=WINDOW_DAYS-1)).isoformat(),
                args.to_date or today.isoformat())
        return
    if args.sample:
        if not args.username:
            parser.error("--sample needs --username")
        sample(args.username, args.sample)
        return
    if args.heading_out:
        gif(heading_frames(), args.heading_out, 125)
    if args.heading_mobile_out:
        gif(heading_frames(mobile=True), args.heading_mobile_out, 125)
    if args.out:
        if not args.config or not args.activity:
            parser.error("--out needs --config and --activity")
        config = json.loads(args.config.read_text())
        data = json.loads(args.activity.read_text())
        if data["username"] != config["username"]:
            parser.error("activity username does not match config")
        gif(frames(config, data, args.seed, args.pattern,
                   asset_root=args.config.resolve().parent, theme=args.theme), args.out,
            FRAME_MS if args.pattern == "shock" else 100)


if __name__ == "__main__":
    main()
