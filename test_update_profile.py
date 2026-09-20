"""The daily publisher must never replace a good public image on failure."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from PIL import Image

import update_profile


NOW = datetime(2026, 9, 20, 3, 0, tzinfo=timezone.utc)


class DailyUpdateTest(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        Image.new("RGBA", (64, 64), (10, 20, 30, 255)).save(self.root / "avatar.png")
        (self.root / "profile-motion.json").write_text(json.dumps({
            "username": "example-user", "icon": "avatar.png",
            "accent": "#e28358", "glow": "#ffe194",
        }))
        self.before = ("A short profile.\n\n" + update_profile.BEGIN + "\n"
                       "<sub>Old capture</sub>\n\n![Old](old.gif)\n" +
                       update_profile.END + "\n\nContact: mailto:hello@example.com\n")
        (self.root / "README.md").write_text(self.before)
        (self.root / "profile-motion.gif").write_bytes(b"previous good GIF")
        (self.root / "profile-motion-dark.gif").write_bytes(b"previous good dark GIF")

    def real_capture(self, username, output, start, end):
        self.assertEqual((username, end), ("example-user", "2026-09-20"))
        begin = NOW.date() - timedelta(days=195)
        days = [{"date": (begin+timedelta(days=n)).isoformat(),
                 "count": n % 8} for n in range(196)]
        output.write_text(json.dumps({
            "username": username, "source": update_profile.SOURCE,
            "observed_at": "2026-09-20T03:00:00Z", "days": days,
        }))

    def run_update(self, capture_fn):
        return update_profile.update(self.root, "profile-motion.json", "README.md",
                                     "profile-motion.gif", "example-user/example-user",
                                     capture_fn=capture_fn, now=NOW)

    def test_success_updates_image_and_cache_busting_url_together(self):
        result = self.run_update(self.real_capture)
        text = (self.root / "README.md").read_text()
        self.assertIn("Captured @example-user", result)
        self.assertIn("https://raw.githubusercontent.com/example-user/example-user/"
                      "main/profile-motion.gif?v=", text)
        self.assertIn("https://raw.githubusercontent.com/example-user/example-user/"
                      "main/profile-motion-dark.gif?v=", text)
        self.assertIn('<source media="(prefers-color-scheme: dark)"', text)
        self.assertIn("Last successful capture 2026-09-20 03:00 UTC", text)
        self.assertIn("Daily refresh scheduled", text)
        self.assertIn("Contact: mailto:hello@example.com", text)
        self.assertEqual(text.count(update_profile.BEGIN), 1)
        with Image.open(self.root / "profile-motion.gif") as gif:
            self.assertEqual(gif.size, (442, 126))
            self.assertGreater(gif.n_frames, 200)
        with Image.open(self.root / "profile-motion-dark.gif") as gif:
            self.assertEqual(gif.size, (442, 126))
            self.assertGreater(gif.n_frames, 200)

    def test_capture_failure_keeps_previous_public_files(self):
        def fail(*_):
            raise RuntimeError("GraphQL unavailable")
        with self.assertRaisesRegex(RuntimeError, "GraphQL unavailable"):
            self.run_update(fail)
        self.assertEqual((self.root / "README.md").read_text(), self.before)
        self.assertEqual((self.root / "profile-motion.gif").read_bytes(),
                         b"previous good GIF")
        self.assertEqual((self.root / "profile-motion-dark.gif").read_bytes(),
                         b"previous good dark GIF")

    def test_synthetic_response_is_not_a_silent_fallback(self):
        def synthetic(*args):
            self.real_capture(*args)
            path = args[1]
            payload = json.loads(path.read_text())
            payload["source"] = "SYNTHETIC example"
            path.write_text(json.dumps(payload))
        with self.assertRaisesRegex(ValueError, "not real GitHub data"):
            self.run_update(synthetic)
        self.assertEqual((self.root / "README.md").read_text(), self.before)
        self.assertEqual((self.root / "profile-motion.gif").read_bytes(),
                         b"previous good GIF")
        self.assertEqual((self.root / "profile-motion-dark.gif").read_bytes(),
                         b"previous good dark GIF")

    def test_dark_render_failure_preserves_both_previous_images(self):
        actual_gif = update_profile.render.gif

        def fail_dark(images, destination, duration):
            if destination.name == "dark.gif":
                raise RuntimeError("dark render failed")
            return actual_gif(images, destination, duration)

        with patch.object(update_profile.render, "gif", side_effect=fail_dark):
            with self.assertRaisesRegex(RuntimeError, "dark render failed"):
                self.run_update(self.real_capture)
        self.assertEqual((self.root / "README.md").read_text(), self.before)
        self.assertEqual((self.root / "profile-motion.gif").read_bytes(),
                         b"previous good GIF")
        self.assertEqual((self.root / "profile-motion-dark.gif").read_bytes(),
                         b"previous good dark GIF")


if __name__ == "__main__":
    unittest.main()
