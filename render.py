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
W, H = 580, 164
STEP, X0, Y0 = 17, 40, 33
HEADING = "Technical Boundary Audit & Repair for AI Systems"
FRAME_MS = 80
WALK_SPEED = 13
EDGE_MARGIN = 31  # entire awake sprite and its shadow clear the right edge
STRIDE = (W + 2*EDGE_MARGIN) / 24  # gait phase completes 24 cycles around a wrap
B_PAUSE_FRAMES = 5


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
             "contributionDays { date contributionCount } } } } } }")
    result = subprocess.run(["gh", "api", "graphql", "-f", "query=" + query],
                            check=True, capture_output=True, text=True)
    response = json.loads(result.stdout)
    if response.get("errors"):
        raise ValueError("GitHub GraphQL error: " + str(response["errors"]))
    user = response.get("data", {}).get("user")
    if user is None:
        raise ValueError("GitHub user not found or not accessible: " + username)
    weeks = user["contributionsCollection"]["contributionCalendar"]["weeks"]
    days = [dict(date=day["date"], count=day["contributionCount"])
            for week in weeks for day in week["contributionDays"]]
    payload = {"username": username, "source": "GitHub GraphQL contributionsCollection snapshot",
               "observed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "days": days}
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def sample(username, output):
    """Explicitly synthetic activity for testing customization, never real data."""
    from datetime import date, timedelta
    start = date(2026, 3, 8)
    days = [dict(date=(start+timedelta(days=i)).isoformat(),
                 count=(i*7 % 13 if i % 4 else 0)) for i in range(196)]
    payload = {"username": username, "source": "SYNTHETIC example, not a GitHub contribution claim",
               "observed_at": "synthetic", "days": days}
    output.write_text(json.dumps(payload, indent=2) + "\n")


def activity_grid(data):
    entries = {d["date"]: d["count"] for d in data["days"]}
    if len(entries) != len(data["days"]) or any(type(v) is not int or v < 0 for v in entries.values()):
        raise ValueError("Activity dates must be unique, with nonnegative integer counts")
    # Input is a dated snapshot. Explicitly render only its final 28 calendar weeks.
    dates = sorted(entries)
    if not dates:
        raise ValueError("No activity days")
    from datetime import date, timedelta
    end = date.fromisoformat(dates[-1])
    sunday = end - timedelta(days=(end.weekday()+1) % 7)
    first = sunday - timedelta(weeks=27)
    return [[entries.get((first + timedelta(weeks=col, days=row)).isoformat(), 0)
             for row in range(7)] for col in range(28)]


def base_frame(username, data, accent):
    bg = (17, 23, 37)
    im = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((1, 1, W-2, H-2), radius=16, outline=(59, 72, 95), width=2)
    d.text((X0, 9), "@" + username, fill=(232, 239, 249), font=font(15, True))
    d.text((W-112, 11), "ACTIVITY", fill=(170, 185, 203), font=font(11, True))
    grid = activity_grid(data)
    shades = [(39, 49, 68), blend((45, 56, 73), accent, .29),
              blend((45, 56, 73), accent, .48), blend((45, 56, 73), accent, .72), accent]
    for col in range(28):
        for row in range(7):
            n = grid[col][row]
            level = 0 if n == 0 else 1 if n < 3 else 2 if n < 6 else 3 if n < 10 else 4
            x, y = X0 + col*STEP, Y0 + row*STEP
            d.rounded_rectangle((x, y, x+12, y+12), radius=3, fill=shades[level])
    d.text((X0, 148), data.get("observed_at", "sample")[:10] + " snapshot  ·  glow = illustration, counts unchanged",
           fill=(161, 178, 199), font=font(10))
    return im, grid


def target_points(grid, seed):
    active = [(c, r) for c in range(2, 27) for r in range(1, 6) if grid[c][r] > 0]
    if not active:
        active = [(8, 3), (21, 4)]
    rng = random.Random(seed)
    first = rng.choice(active[:max(1, len(active)//2)])
    second = rng.choice(active[max(1, len(active)//2):] or active)
    return [first, second]


def position(target, t):
    # Two visits: approach, touch/glow, pause; common motion for any icon.
    anchors = [(0, (10, 3)), (13, target[0]), (20, target[0]),
               (31, target[0]), (45, target[1]), (53, target[1]), (65, target[1])]
    for (f0, p0), (f1, p1) in zip(anchors, anchors[1:]):
        if t <= f1:
            s = (t-f0)/(f1-f0)
            s = s*s*(3-2*s)
            return (p0[0]*(1-s)+p1[0]*s, p0[1]*(1-s)+p1[1]*s)
    return target[1]


def touch_frames(config, data, seed, asset_root=ROOT):
    accent, glow = color(config["accent"]), color(config["glow"])
    base, grid = base_frame(config["username"], data, accent)
    targets = target_points(grid, seed)
    icon = Image.open(asset_root / config["icon"]).convert("RGBA")
    icon.thumbnail((51, 51), Image.Resampling.LANCZOS)
    for t in range(66):
        im = base.copy()
        d = ImageDraw.Draw(im, "RGBA")
        for visit, (start, end) in enumerate(((17, 27), (50, 60))):
            if start <= t <= end:
                c, r = targets[visit]
                x, y = X0 + c*STEP+6, Y0 + r*STEP+6
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
    ranges = (range(8, 13), range(19, 23))
    stops = []
    for scene, columns in enumerate(ranges):
        active = [(col, 3) for col in columns if grid[col][3] > 0]
        stops.append(random.Random(f"{seed}:stop:{scene}").choice(
            active or [(list(columns)[len(columns)//2], 3)]))
    return stops


def shock_plan(grid, seed, stop):
    """One fixed per-cell motion plan: radial launch, irregular voluntary return."""
    cx, cy = X0 + stop[0]*STEP + 6, Y0 + stop[1]*STEP - 17
    plan = []
    for col in range(28):
        for row in range(7):
            x, y = X0 + col*STEP, Y0 + row*STEP
            rng = random.Random(f"{seed}:{col}:{row}")
            dx, dy = x+6-cx, y+6-cy
            dist = math.hypot(dx, dy)
            if dist < 3:
                angle = rng.random()*math.tau
                dx, dy, dist = math.cos(angle), math.sin(angle), 1
            reach = 36 + min(52, dist*.27) + rng.uniform(-6, 8)
            # Slight tangent adds a natural tumble without reversing the burst.
            tangent = rng.uniform(-9, 9)
            ox = dx/dist*reach - dy/dist*tangent
            oy = dy/dist*reach + dx/dist*tangent
            launch = 27 + min(8, int(dist/35))
            return_start = 46 + rng.randrange(0, 17)
            return_duration = 12 + rng.randrange(0, 14)
            plan.append(dict(col=col, row=row, count=grid[col][row], x=x, y=y,
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


def shock_background(username, data):
    im = Image.new("RGB", (W, H), (17, 23, 37))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((1, 1, W-2, H-2), radius=16, outline=(59, 72, 95), width=2)
    d.text((X0, 9), "@"+username, fill=(232, 239, 249), font=font(15, True))
    d.text((W-112, 11), "ACTIVITY", fill=(170, 185, 203), font=font(11, True))
    d.text((X0, 148), data.get("observed_at", "sample")[:10]
           + " snapshot  ·  tile motion is decorative; counts unchanged",
           fill=(161, 178, 199), font=font(10))
    return im


def square_color(count, accent):
    shades = [(39, 49, 68), blend((45, 56, 73), accent, .29),
              blend((45, 56, 73), accent, .48),
              blend((45, 56, 73), accent, .72), accent]
    level = 0 if count == 0 else 1 if count < 3 else 2 if count < 6 else 3 if count < 10 else 4
    return shades[level]


def load_icon(path, asset_root=ROOT):
    icon = Image.open(asset_root / path).convert("RGBA")
    icon.thumbnail((53, 53), Image.Resampling.LANCZOS)
    return icon


def creature_at(frame, icon, x, ground_y, angle=0, scale=1, lift=0):
    size = (max(1, round(icon.width*scale)), max(1, round(icon.height*scale)))
    sprite = icon.resize(size, Image.Resampling.LANCZOS)
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
        stop_x = X0+stop[0]*STEP+6
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


def draw_creature(im, state, awake, sleeping, waking, specialized_sleep):
    x = state["x"]
    ground_y = Y0+3*STEP+6
    d = ImageDraw.Draw(im)
    d.ellipse((round(x-17), ground_y+8, round(x+17), ground_y+12),
              fill=(29, 36, 52))
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


def shock_frames(config, data, seed, asset_root=ROOT):
    """One two-scene timeline: right exit, invisible wrap, left re-entry."""
    accent, glow = color(config["accent"]), color(config["glow"])
    grid = activity_grid(data)
    states = build_timeline(grid, seed)
    plans = [shock_plan(grid, seed+scene*100003, stop)
             for scene, stop in enumerate(scene_stops(grid, seed))]
    background = shock_background(config["username"], data)
    awake = load_icon(config["icon"], asset_root)
    sleeping = load_icon(config["sleep_icon"], asset_root) if config.get("sleep_icon") else awake
    waking = load_icon(config["wake_icon"], asset_root) if config.get("wake_icon") else awake
    for state in states:
        im = background.copy()
        draw = ImageDraw.Draw(im)
        stop_x = X0+state["stop"][0]*STEP+6
        center_y = Y0+3*STEP+6-23
        t = state.get("motion_t", 0)
        plan = plans[state["scene"]]
        for cell in plan:
            x, y = cell_position(cell, t)
            x, y = round(x), round(y)
            draw.rounded_rectangle((x, y, x+12, y+12), radius=3,
                                   fill=square_color(cell["count"], accent))

        # Same background and rendering on both scenes; only the shock center moves.
        for onset in (27, 31):
            age = t-onset
            if 0 <= age <= 15:
                radius = 5+age*13
                strength = (1-age/16)*.75
                ring = blend((17, 23, 37), glow, strength)
                draw.ellipse((stop_x-radius, center_y-radius,
                              stop_x+radius, center_y+radius),
                             outline=ring, width=3 if age < 9 else 2)
        draw_creature(im, state, awake, sleeping, waking,
                      bool(config.get("sleep_icon")))
        yield im


def frames(config, data, seed, pattern="shock", asset_root=ROOT):
    if pattern == "shock":
        return shock_frames(config, data, seed, asset_root)
    if pattern == "touch":
        return touch_frames(config, data, seed, asset_root)
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
    parser.add_argument("--out", type=Path, help="Output activity GIF")
    parser.add_argument("--heading-out", type=Path, help="Output heading GIF")
    parser.add_argument("--heading-mobile-out", type=Path, help="Output two-line narrow-screen heading GIF")
    parser.add_argument("--capture", type=Path, help="Capture dated GraphQL snapshot to path, then stop")
    parser.add_argument("--username", help="Username for --capture")
    parser.add_argument("--sample", type=Path, help="Write synthetic activity for --username, then stop")
    parser.add_argument("--from-date", help="Snapshot start, YYYY-MM-DD (default: 195 days before today, UTC)")
    parser.add_argument("--to-date", help="Snapshot end, YYYY-MM-DD (default: today, UTC)")
    args = parser.parse_args()
    if args.capture:
        if not args.username:
            parser.error("--capture needs --username")
        today = datetime.now(timezone.utc).date()
        capture(args.username, args.capture,
                args.from_date or (today-timedelta(days=195)).isoformat(),
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
                   asset_root=args.config.resolve().parent), args.out,
            FRAME_MS if args.pattern == "shock" else 100)


if __name__ == "__main__":
    main()
