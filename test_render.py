import json
import hashlib
import math
import unittest
from unittest.mock import patch
from tempfile import TemporaryDirectory
from pathlib import Path
from PIL import Image
import render

ROOT = Path(__file__).parent


class RenderTest(unittest.TestCase):
    def test_profile_icon_can_live_beside_an_external_config(self):
        with TemporaryDirectory() as directory:
            asset_root = Path(directory)
            Image.new("RGBA", (64, 64), (231, 105, 65, 255)).save(asset_root / "avatar.png")
            config = {"username": "example-user", "icon": "avatar.png",
                      "accent": "#e28358", "glow": "#ffe194"}
            data = json.loads((ROOT / "example_activity.json").read_text())
            images = list(render.frames(config, data, 216, asset_root=asset_root))
            self.assertGreater(len(images), 200)
            self.assertNotEqual(images[0].tobytes(), images[20].tobytes())

    def test_capture_writes_dated_public_snapshot_and_rejects_bad_dates(self):
        response = {"data": {"user": {"contributionsCollection": {
            "contributionCalendar": {"weeks": [{"contributionDays": [
                {"date": "2026-09-19", "contributionCount": 3}
            ]}]}}}}}
        with TemporaryDirectory() as directory:
            output = Path(directory) / "capture.json"
            with patch.object(render.subprocess, "run") as run:
                run.return_value.stdout = json.dumps(response)
                render.capture("example-user", output, "2026-09-19", "2026-09-20")
                self.assertEqual(json.loads(output.read_text())["days"],
                                 [{"date": "2026-09-19", "count": 3}])
                command = run.call_args.args[0]
                self.assertEqual(command[:3], ["gh", "api", "graphql"])
                self.assertIn('user(login: "example-user")', command[4])
                self.assertRaises(ValueError, render.capture, "example-user", output,
                                  "2026-09-20", "2026-09-19")
                self.assertEqual(run.call_count, 1)

    def test_data_is_not_changed_and_seed_replays_frames(self):
        config = json.loads((ROOT / "cat.json").read_text())
        input_path = ROOT / "shin_activity_2026-09-20.json"
        before = input_path.read_bytes()
        data = json.loads(before)
        states = render.build_timeline(render.activity_grid(data), 216)
        first = list(render.frames(config, data, 216))
        digest = lambda im: hashlib.sha256(im.tobytes()).digest()
        self.assertEqual(len(first), len(states))
        self.assertEqual([digest(im) for im in first],
                         [digest(im) for im in render.frames(config, data, 216)])
        self.assertNotEqual(first[0].tobytes(), first[-1].tobytes())
        self.assertEqual({im.getpixel((4, 4)) for im in first}, {(17, 23, 37)})
        self.assertEqual(input_path.read_bytes(), before)
        self.assertTrue(any(day["count"] > 0 for day in data["days"]))

    def test_two_scenes_walk_right_and_both_wraps_continue_without_reset(self):
        data = json.loads((ROOT / "shin_activity_2026-09-20.json").read_text())
        grid = render.activity_grid(data)
        states = render.build_timeline(grid, 216)
        self.assertEqual({state["scene"] for state in states}, {0, 1})
        a, b = render.scene_stops(grid, 216)
        self.assertLess(render.X0+a[0]*render.STEP, render.W/2)
        self.assertGreater(render.X0+b[0]*render.STEP, render.W/2)
        seam = next(i for i in range(1, len(states))
                    if states[i-1]["scene"] != states[i]["scene"])
        frames = list(render.frames(json.loads((ROOT / "cat.json").read_text()), data, 216))
        doubled = frames + frames  # decoded two-cycle playback order
        awake = render.load_icon("crowned_cat.png")
        opaque = awake.getbbox()
        self.assertIsNotNone(opaque)
        for left, right in ((seam-1, seam), (len(states)-1, len(states))):
            outgoing = states[left % len(states)]
            incoming = states[right % len(states)]
            self.assertEqual((outgoing["stage"], incoming["stage"]), ("exit", "enter"))
            self.assertEqual(outgoing["x"], render.W+render.EDGE_MARGIN)
            self.assertEqual(incoming["x"], -render.EDGE_MARGIN+render.WALK_SPEED)
            self.assertGreater(outgoing["x"]-awake.width/2+opaque[0], render.W)
            self.assertGreater(outgoing["x"]-17, render.W)
            self.assertGreater(incoming["x"]-awake.width/2+opaque[2], 0)
            # In unwrapped coordinates both boundaries advance one walk step.
            self.assertEqual(incoming["x"]+render.W+2*render.EDGE_MARGIN-outgoing["x"],
                             render.WALK_SPEED)
            phase_delta = (render.walk_phase(incoming["x"])-
                           render.walk_phase(outgoing["x"])) % math.tau
            self.assertAlmostEqual(phase_delta,
                                   math.tau*render.WALK_SPEED/render.STRIDE)
            # The card and restored squares never blink or reset at either seam.
            self.assertEqual(doubled[left].crop((36, 0, render.W, render.H)).tobytes(),
                             doubled[right].crop((36, 0, render.W, render.H)).tobytes())
            self.assertNotEqual(doubled[left].tobytes(), doubled[right].tobytes())
        for scene in (0, 1):
            walks = [s["x"] for s in states if s["scene"] == scene and s["stage"] in ("enter", "exit")]
            self.assertTrue(all(later >= earlier for earlier, later in zip(walks, walks[1:])))
        # Decode the actual GIF, expand durations to ticks, then inspect two
        # consecutive cycles. This catches palette-induced seam flicker that
        # comparing the RGB source frames alone would miss.
        decoded, encoded_durations = [], []
        with Image.open(ROOT / "crowned_cat.gif") as gif:
            for i in range(gif.n_frames):
                gif.seek(i)
                duration = gif.info["duration"]
                self.assertEqual(duration % render.FRAME_MS, 0)
                ticks = duration // render.FRAME_MS
                decoded.extend([gif.convert("RGB").copy()] * ticks)
                encoded_durations.extend([duration] * ticks)
        self.assertEqual(len(decoded), len(states))
        playback = decoded + decoded
        for left, right in ((seam-1, seam), (len(states)-1, len(states))):
            # The entire creature clears the right edge. A bounded two-tick
            # (160 ms) empty handoff is allowed; a long end-card pause is not.
            self.assertLessEqual(encoded_durations[left], 2*render.FRAME_MS)
            self.assertEqual(encoded_durations[right % len(states)], render.FRAME_MS)
            self.assertEqual(playback[left].crop((36, 0, render.W, render.H)).tobytes(),
                             playback[right].crop((36, 0, render.W, render.H)).tobytes())
            self.assertNotEqual(playback[left].tobytes(), playback[right].tobytes())
            blank = playback[left].tobytes()
            blank_ticks = 0
            for tick in range(left, left-4, -1):
                if playback[tick].tobytes() != blank:
                    break
                blank_ticks += 1
            self.assertLessEqual(blank_ticks, 2)

    def test_burst_return_and_single_b_pause_preserve_each_cell(self):
        data = json.loads((ROOT / "shin_activity_2026-09-20.json").read_text())
        grid = render.activity_grid(data)
        stops = render.scene_stops(grid, 216)
        states = render.build_timeline(grid, 216)
        for scene, stop in enumerate(stops):
            plan = render.shock_plan(grid, 216+scene*100003, stop)
            self.assertEqual(len(plan), 196)
            self.assertEqual([cell["count"] for cell in plan],
                             [grid[col][row] for col in range(28) for row in range(7)])
            self.assertGreater(len({cell["return_start"] for cell in plan}), 10)
            self.assertGreater(len({cell["return_end"] for cell in plan}), 15)
            for t in (0, 87):
                self.assertTrue(all(render.cell_position(cell, t) == (cell["x"], cell["y"])
                                    for cell in plan))
            burst = [(render.cell_position(cell, 36)[0]-cell["x"],
                      render.cell_position(cell, 36)[1]-cell["y"]) for cell in plan]
            for axis in (0, 1):
                self.assertGreater(sum(delta[axis] > 0 for delta in burst), 25)
                self.assertGreater(sum(delta[axis] < 0 for delta in burst), 25)
            home_at_72 = sum(render.cell_position(cell, 72) == (cell["x"], cell["y"])
                             for cell in plan)
            self.assertGreater(home_at_72, 0)
            self.assertLess(home_at_72, len(plan))
        self.assertFalse(any(state.get("pause_step", 0) for state in states if state["scene"] == 0))
        paused = [state for state in states if state["scene"] == 1 and
                  state.get("motion_t") == 62]
        self.assertEqual([state["pause_step"] for state in paused], list(range(6)))
        self.assertTrue(any(render.cell_position(cell, 62) != (cell["x"], cell["y"])
                            for cell in render.shock_plan(grid, 216+100003, stops[1])))
        pause_indices = [i for i, state in enumerate(states) if state in paused]
        cat = json.loads((ROOT / "cat.json").read_text())
        frames = list(render.frames(cat, data, 216))
        stop_x = render.X0+stops[1][0]*render.STEP+6
        for index in pause_indices[1:]:
            self.assertEqual(
                frames[index].crop((0, 0, stop_x-45, render.H)).tobytes(),
                frames[pause_indices[0]].crop((0, 0, stop_x-45, render.H)).tobytes())
            self.assertEqual(
                frames[index].crop((stop_x+45, 0, render.W, render.H)).tobytes(),
                frames[pause_indices[0]].crop((stop_x+45, 0, render.W, render.H)).tobytes())
        self.assertNotEqual(frames[pause_indices[0]].tobytes(),
                            frames[pause_indices[2]].tobytes())

    def test_alternate_icon_colors_and_gif_frames(self):
        cat = json.loads((ROOT / "cat.json").read_text())
        fox = json.loads((ROOT / "fox.json").read_text())
        self.assertNotEqual(cat["icon"], fox["icon"])
        self.assertNotEqual(cat["accent"], fox["accent"])
        self.assertNotEqual(cat["glow"], fox["glow"])
        self.assertIn("sleep_icon", cat)
        self.assertIn("wake_icon", cat)
        self.assertNotIn("sleep_icon", fox)
        self.assertNotIn("wake_icon", fox)
        self.assertNotEqual((ROOT / cat["sleep_icon"]).read_bytes(),
                            (ROOT / cat["icon"]).read_bytes())
        data = json.loads((ROOT / "example_activity.json").read_text())
        self.assertIn("SYNTHETIC", data["source"])
        self.assertEqual(fox["username"], data["username"])
        frames = list(render.frames(fox, data, 216))
        self.assertNotEqual(frames[0].tobytes(), frames[20].tobytes())
        fox_states = render.build_timeline(render.activity_grid(data), 216)
        expected = len(fox_states)
        for name, n in (("crowned_cat.gif", len(render.build_timeline(render.activity_grid(
                            json.loads((ROOT / "shin_activity_2026-09-20.json").read_text())), 216))),
                        ("fox.gif", expected),
                        ("crowned_cat_touch.gif", 66), ("heading.gif", 40),
                        ("heading_mobile.gif", 40)):
            with Image.open(ROOT / name) as gif:
                # GIF encoding can coalesce visually identical adjacent frames.
                self.assertGreaterEqual(gif.n_frames, n-12)
                self.assertLessEqual(gif.n_frames, n)
                self.assertEqual(gif.info["loop"], 0)
                if name in ("crowned_cat.gif", "fox.gif"):
                    durations, decoded = [], []
                    for i in range(gif.n_frames):
                        gif.seek(i)
                        duration = gif.info["duration"]
                        durations.append(duration)
                        if name == "fox.gif":
                            decoded.extend([gif.convert("RGB").copy()] *
                                           (duration // render.FRAME_MS))
                    self.assertEqual(sum(durations), n*render.FRAME_MS)
                    self.assertEqual(durations[0], render.FRAME_MS)
                    self.assertLessEqual(durations[-1], 2*render.FRAME_MS)
                    self.assertLess((ROOT / name).stat().st_size, 5_000_000)
                    if name == "fox.gif":
                        seam = next(i for i in range(1, len(fox_states))
                                    if fox_states[i-1]["scene"] != fox_states[i]["scene"])
                        self.assertEqual(len(decoded), len(fox_states))
                        two_cycles = decoded + decoded
                        for left, right in ((seam-1, seam), (len(decoded)-1, len(decoded))):
                            self.assertEqual(
                                two_cycles[left].crop((36, 0, render.W, render.H)).tobytes(),
                                two_cycles[right].crop((36, 0, render.W, render.H)).tobytes())

if __name__ == "__main__":
    unittest.main()
