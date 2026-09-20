"""Capture real GitHub contributions and stage one fail-closed profile update.

Only the caller's repository is writable. The workflow commits and pushes the
GIF and README together *after* this program returns successfully.
"""

import argparse
from datetime import date, datetime, timedelta, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import quote

from PIL import Image

import render


BEGIN = "<!-- profile-motion:begin -->"
END = "<!-- profile-motion:end -->"
SOURCE = "GitHub GraphQL contributionsCollection snapshot"
LOGIN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\Z")
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
BRANCH = re.compile(r"[A-Za-z0-9._/-]+\Z")


def in_repository(root, name):
    path = Path(name)
    if path.is_absolute():
        raise ValueError("Use a path relative to the profile repository")
    resolved = (root / path).resolve()
    if resolved == root or not resolved.is_relative_to(root):
        raise ValueError("Path must stay inside the profile repository")
    return resolved


def update(profile_root, config_name, readme_name, output_name, repository,
           branch="main", capture_fn=render.capture, now=None):
    root = Path(profile_root).resolve()
    if not REPOSITORY.fullmatch(repository) or not BRANCH.fullmatch(branch):
        raise ValueError("Expected OWNER/REPO and a normal branch name")
    config_path = in_repository(root, config_name)
    readme_path = in_repository(root, readme_name)
    output_path = in_repository(root, output_name)
    if output_path.suffix.lower() != ".gif":
        raise ValueError("Output must be a GIF")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    username = config["username"]
    if not isinstance(username, str) or not LOGIN.fullmatch(username):
        raise ValueError("Config needs a valid GitHub username")
    for key in ("icon", "sleep_icon", "wake_icon"):
        if key in config:
            icon = in_repository(root, config_path.parent.relative_to(root) / config[key])
            if not icon.is_file():
                raise ValueError(f"Missing {key}: {icon}")
    alt = config.get("alt", f"Animated GitHub contributions for @{username}")
    if not isinstance(alt, str) or not alt.strip() or any(c in alt for c in "\r\n]"):
        raise ValueError("alt must be a nonempty single-line Markdown image label")

    original = readme_path.read_text(encoding="utf-8")
    if original.count(BEGIN) != 1 or original.count(END) != 1:
        raise ValueError("README needs exactly one profile-motion marker pair")
    before, remainder = original.split(BEGIN, 1)
    _, after = remainder.split(END, 1)
    current = now or datetime.now(timezone.utc)
    today = current.date()

    # No fallback to --sample: capture, validation and GIF encoding must all
    # succeed before a single publishable file is modified.
    with tempfile.TemporaryDirectory(prefix="profile-motion-") as temporary:
        activity = Path(temporary) / "activity.json"
        generated = Path(temporary) / "generated.gif"
        capture_fn(username, activity, (today-timedelta(days=195)).isoformat(),
                   today.isoformat())
        data = json.loads(activity.read_text(encoding="utf-8"))
        if data.get("username") != username or data.get("source") != SOURCE:
            raise ValueError("Capture was not real GitHub data for the configured user")
        observed = datetime.fromisoformat(data["observed_at"].replace("Z", "+00:00"))
        if observed.tzinfo is None or abs((observed-current).total_seconds()) > 1800:
            raise ValueError("Capture timestamp is missing or stale")
        days = sorted(date.fromisoformat(entry["date"]) for entry in data["days"])
        render.activity_grid(data)  # uniqueness and nonnegative integer counts
        if not days or days[-1] < today-timedelta(days=1) or days[-1] > today:
            raise ValueError("Capture does not reach the current contribution window")

        render.gif(render.frames(config, data, 216, "shock", config_path.parent),
                   generated, render.FRAME_MS)
        with Image.open(generated) as result:
            if result.size != (render.W, render.H) or result.n_frames < 2:
                raise ValueError("Generated GIF has no usable animation")
        gif_bytes = generated.read_bytes()
        digest = hashlib.sha256(gif_bytes).hexdigest()[:16]
        image_url = ("https://raw.githubusercontent.com/" + repository + "/" +
                     quote(branch, safe="/") + "/" +
                     quote(output_path.relative_to(root).as_posix(), safe="/") +
                     "?v=" + digest)
        caption = (f"@{username}'s GitHub contribution snapshot · {days[0]}–{days[-1]} · "
                   f"Last successful capture {observed.astimezone(timezone.utc):%Y-%m-%d %H:%M} UTC "
                   "· Daily refresh scheduled")
        replacement = (BEGIN + "\n" + f"<sub>{html.escape(caption, quote=False)}</sub>\n\n" +
                       f"![{alt}]({image_url})\n" + END)
        updated = before + replacement + after

        # GitHub publishes only after the caller commits both paths. A failed
        # capture/render/README validation leaves the previous public GIF intact.
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(gif_bytes)
        readme_path.write_text(updated, encoding="utf-8")

    result = (f"Captured @{username} at {observed:%Y-%m-%dT%H:%M:%SZ}; "
              f"days {days[0]}–{days[-1]}; GIF SHA-256 {digest}")
    print(result)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a", encoding="utf-8") as stream:
            stream.write(f"### Profile motion\n\n{html.escape(result)}\n\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile-root", type=Path, required=True)
    parser.add_argument("--config", default="profile-motion.json")
    parser.add_argument("--readme", default="README.md")
    parser.add_argument("--output", default="profile-motion.gif")
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--branch", default=os.environ.get("GITHUB_REF_NAME", "main"))
    args = parser.parse_args()
    if not args.repository:
        parser.error("--repository or GITHUB_REPOSITORY is required")
    update(args.profile_root, args.config, args.readme, args.output,
           args.repository, args.branch)


if __name__ == "__main__":
    main()
