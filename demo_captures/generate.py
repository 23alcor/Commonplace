#!/usr/bin/env python3
"""Generate synthetic, unprepared-looking demo captures for capture-to-vault.

Outputs land in this directory. Requires: Pillow, numpy, espeak-ng, ffmpeg.
"""

from __future__ import annotations

import math
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent
FONT_SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_SANS_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def add_noise(img: Image.Image, sigma: float = 12.0) -> Image.Image:
    arr = np.asarray(img).astype(np.float32)
    noise = np.random.default_rng(42).normal(0, sigma, arr.shape)
    out = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(out)


def skew_perspective(img: Image.Image, strength: float = 0.06) -> Image.Image:
    w, h = img.size
    dx = int(w * strength)
    dy = int(h * strength * 0.4)
    src = (0, 0, w, 0, w, h, 0, h)
    dst = (dx, dy, w - dx // 2, 0, w - dx, h - dy, dx // 3, h)
    return img.transform(
        (w, h),
        Image.Transform.PERSPECTIVE,
        _find_coeffs(src, dst),
        Image.Resampling.BICUBIC,
        fillcolor=(235, 232, 220),
    )


def _find_coeffs(src: tuple[int, ...], dst: tuple[int, ...]) -> list[float]:
    # Map src quad -> dst quad for Image.Transform.PERSPECTIVE
    matrix = []
    for i in range(4):
        x, y = dst[2 * i], dst[2 * i + 1]
        u, v = src[2 * i], src[2 * i + 1]
        matrix.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        matrix.append([0, 0, 0, x, y, 1, -v * x, -v * y])
    A = np.array(matrix, dtype=np.float64)
    B = np.array(src, dtype=np.float64)
    return np.linalg.lstsq(A, B, rcond=None)[0].tolist()


def paper_bg(size: tuple[int, int], tint: tuple[int, int, int] = (248, 244, 230)) -> Image.Image:
    img = Image.new("RGB", size, tint)
    draw = ImageDraw.Draw(img)
    rng = np.random.default_rng(7)
    for y in range(0, size[1], 36):
        draw.line([(40, y), (size[0] - 20, y)], fill=(210, 220, 230), width=1)
    for _ in range(80):
        x, y = int(rng.integers(0, size[0])), int(rng.integers(0, size[1]))
        draw.point((x, y), fill=(200, 190, 170))
    return img


def make_voice(path: Path, text: str, seed: int = 0) -> None:
    """TTS via espeak-ng, then add room noise + slight compression to WAV."""
    with tempfile.TemporaryDirectory() as td:
        clean = Path(td) / "clean.wav"
        noisy = Path(td) / "noisy.wav"
        subprocess.run(
            [
                "espeak-ng",
                "-v",
                "en-us",
                "-s",
                "155",
                "-p",
                "45",
                "-w",
                str(clean),
                text,
            ],
            check=True,
        )
        # Mix low-level pink noise + band-limit so it sounds like a phone memo.
        af = (
            f"anoisesrc=color=pink:sample_rate=22050:duration=30:amplitude=0.02:seed={seed}[n];"
            f"[0:a][n]amix=inputs=2:duration=first:dropout_transition=0,"
            f"highpass=f=120,lowpass=f=3800,volume=1.1"
        )
        proc = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(clean),
                "-filter_complex",
                af,
                "-ar",
                "22050",
                "-ac",
                "1",
                str(noisy),
            ],
            capture_output=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.decode()[-800:])
        path.write_bytes(noisy.read_bytes())


def make_whiteboard_regularization(path: Path) -> None:
    img = Image.new("RGB", (1400, 1000), (245, 248, 250))
    draw = ImageDraw.Draw(img)
    # Board frame + markers tray
    draw.rectangle([40, 40, 1360, 920], fill=(252, 253, 255), outline=(90, 90, 95), width=6)
    draw.rectangle([40, 920, 1360, 960], fill=(70, 70, 75))
    title = font(FONT_SANS_BOLD, 54)
    body = font(FONT_SANS, 40)
    scribble = font(FONT_SANS, 34)
    draw.text((120, 90), "Regularization (EECE 448)", fill=(30, 60, 140), font=title)
    lines = [
        "L2  -> shrinks weights (ridge)",
        "L1  -> sparse / some weights -> 0",
        "Dropout -> randomly disable units",
        "Early stop on val curve",
        "",
        "Q: when does L1 beat L2?",
        "   -> feature selection / noisy feats",
    ]
    y = 200
    colors = [(25, 25, 25), (25, 25, 25), (160, 40, 40), (25, 25, 25), (25, 25, 25), (20, 90, 40), (20, 90, 40)]
    for line, color in zip(lines, colors):
        # Slight horizontal jitter per line to look hand-drawn with a marker
        jitter = int(4 * math.sin(y / 40))
        draw.text((130 + jitter, y), line, fill=color, font=body if line else scribble)
        y += 85
    # Eraser smudge + stray dots
    draw.ellipse([1100, 700, 1280, 820], fill=(235, 238, 242))
    draw.line([(200, 780), (520, 800)], fill=(180, 40, 40), width=3)
    img = skew_perspective(img, 0.045)
    img = img.filter(ImageFilter.GaussianBlur(radius=1.4))
    img = add_noise(img, 8)
    img = ImageEnhance.Contrast(img).enhance(0.92)
    img.save(path, quality=88)


def make_whiteboard_batcave(path: Path) -> None:
    img = Image.new("RGB", (1280, 900), (236, 240, 244))
    draw = ImageDraw.Draw(img)
    draw.rectangle([30, 30, 1250, 850], fill=(250, 252, 255), outline=(60, 60, 65), width=5)
    h = font(FONT_SANS_BOLD, 48)
    b = font(FONT_SANS, 36)
    draw.text((90, 70), "Batcave D1 — rate limit", fill=(20, 20, 20), font=h)
    bullets = [
        "hit free-tier read cap ~7am",
        "cause: polling overview every 5s",
        "fix:",
        "  1) cache overview 60s",
        "  2) batch habit reads",
        "  3) stop N+1 on dashboard",
        "owner: dashboard worker",
    ]
    y = 170
    for line in bullets:
        draw.text((110, y), "•  " + line if not line.startswith(" ") else line, fill=(35, 35, 40), font=b)
        y += 70
    draw.rectangle([860, 200, 1180, 480], outline=(200, 50, 50), width=4)
    draw.text((880, 220), "BEFORE", fill=(200, 50, 50), font=font(FONT_SANS_BOLD, 28))
    draw.text((880, 280), "reads/min", fill=(40, 40, 40), font=b)
    draw.text((880, 340), "~~ 400+", fill=(200, 50, 50), font=font(FONT_SANS_BOLD, 44))
    img = skew_perspective(img, 0.055)
    img = img.filter(ImageFilter.GaussianBlur(1.6))
    img = add_noise(img, 10)
    img.save(path, quality=85)


def _wobbly_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    fill: tuple[int, int, int],
    fnt: ImageFont.FreeTypeFont,
    seed: int,
) -> None:
    rng = np.random.default_rng(seed)
    x, y = xy
    for i, ch in enumerate(text):
        oy = int(rng.integers(-2, 3))
        ox = int(rng.integers(-1, 2))
        draw.text((x + ox, y + oy), ch, fill=fill, font=fnt)
        bbox = draw.textbbox((0, 0), ch, font=fnt)
        x += bbox[2] - bbox[0] + int(rng.integers(0, 2))


def make_handwritten_interview(path: Path) -> None:
    img = paper_bg((1100, 1400))
    draw = ImageDraw.Draw(img)
    f = font(FONT_SERIF, 42)
    _wobbly_text(draw, (90, 80), "Interview prep — this week", (25, 40, 90), f, 1)
    notes = [
        "Mon: LC two-sum variants (C++)",
        "Tue: sliding window + mocks?",
        "Wed: system design — rate limiter",
        "Thu: LC graphs / BFS",
        "Fri: mock interview (peer)",
        "",
        "Track apps in Job Search Pipeline",
        "Target: GPU / infra firms",
        "",
        "Don't skip daily LC — even 1.",
    ]
    y = 180
    for i, line in enumerate(notes):
        _wobbly_text(draw, (100, y), line, (30, 30, 30), font(FONT_SERIF, 36), 10 + i)
        y += 95
    # Coffee ring
    draw.ellipse([820, 1100, 980, 1260], outline=(190, 160, 120), width=3)
    img = img.rotate(2.2, expand=True, fillcolor=(248, 244, 230))
    img = skew_perspective(img, 0.03)
    img = img.filter(ImageFilter.GaussianBlur(0.9))
    img = add_noise(img, 14)
    img = ImageEnhance.Brightness(img).enhance(0.97)
    img.convert("RGB").save(path, quality=82)


def make_handwritten_study(path: Path) -> None:
    img = paper_bg((1000, 1300), (250, 247, 235))
    draw = ImageDraw.Draw(img)
    _wobbly_text(draw, (80, 70), "Study session 11/21", (40, 40, 40), font(FONT_SERIF, 40), 3)
    lines = [
        "EECE 448 — finish lab before Wed",
        "Reviewed momentum vs Adam",
        "Practice:",
        "  - GD with noisy grads",
        "  - when LR diverges",
        "",
        "Next: regularization chapter",
        "Link back to Gradient Descent Notes",
    ]
    y = 170
    for i, line in enumerate(lines):
        _wobbly_text(draw, (90, y), line, (25, 25, 25), font(FONT_SERIF, 34), 20 + i)
        y += 100
    img = img.rotate(-1.8, expand=True, fillcolor=(250, 247, 235))
    img = skew_perspective(img, 0.04)
    img = img.filter(ImageFilter.GaussianBlur(1.1))
    img = add_noise(img, 16)
    img.convert("RGB").save(path, quality=80)


def make_phone_screenshot_jobs(path: Path) -> None:
    # Tall phone canvas with status bar + faux app UI
    w, h = 1170, 2532
    img = Image.new("RGB", (w, h), (245, 245, 247))
    draw = ImageDraw.Draw(img)
    # Status bar
    draw.rectangle([0, 0, w, 90], fill=(245, 245, 247))
    draw.text((60, 28), "9:41", fill=(0, 0, 0), font=font(FONT_SANS_BOLD, 36))
    draw.text((920, 28), "5G  84%", fill=(0, 0, 0), font=font(FONT_SANS, 32))
    # App header
    draw.rectangle([0, 90, w, 260], fill=(20, 80, 180))
    draw.text((60, 140), "Applications", fill=(255, 255, 255), font=font(FONT_SANS_BOLD, 64))
    rows = [
        ("ChipCo — SWE intern", "Screen", (40, 140, 80)),
        ("CloudForge — ML platform", "Applied", (60, 100, 180)),
        ("TradeDesk Infra", "Found", (120, 120, 120)),
        ("GPU Labs — systems", "Technical", (180, 100, 30)),
        ("EdgeNet — edge runtime", "Applied", (60, 100, 180)),
    ]
    y = 300
    for title, stage, color in rows:
        draw.rounded_rectangle([48, y, w - 48, y + 220], radius=28, fill=(255, 255, 255))
        draw.text((90, y + 40), title, fill=(20, 20, 20), font=font(FONT_SANS_BOLD, 40))
        draw.rounded_rectangle([90, y + 120, 90 + 260, y + 180], radius=16, fill=color)
        draw.text((120, y + 132), stage, fill=(255, 255, 255), font=font(FONT_SANS_BOLD, 32))
        draw.text((900, y + 90), "›", fill=(180, 180, 180), font=font(FONT_SANS, 60))
        y += 250
    # Soft phone-cam look: slight vignette + jpeg mush
    img = ImageEnhance.Color(img).enhance(0.95)
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    img = add_noise(img, 4)
    img.save(path, quality=70)


def make_phone_screenshot_tailscale(path: Path) -> None:
    w, h = 1170, 2000
    img = Image.new("RGB", (w, h), (18, 18, 20))
    draw = ImageDraw.Draw(img)
    draw.text((60, 40), "9:41", fill=(230, 230, 230), font=font(FONT_SANS_BOLD, 34))
    draw.text((80, 140), "Tailscale", fill=(255, 255, 255), font=font(FONT_SANS_BOLD, 72))
    draw.text((80, 240), "Connected · MagicDNS on", fill=(80, 200, 120), font=font(FONT_SANS, 40))
    machines = [
        ("home-pc", "100.64.0.12", "active"),
        ("laptop", "100.64.0.34", "active"),
        ("pi-hole", "100.64.0.51", "idle"),
    ]
    y = 360
    for name, ip, state in machines:
        draw.rounded_rectangle([48, y, w - 48, y + 200], radius=24, fill=(40, 40, 44))
        draw.text((90, y + 40), name, fill=(255, 255, 255), font=font(FONT_SANS_BOLD, 44))
        draw.text((90, y + 110), ip, fill=(160, 160, 170), font=font(FONT_MONO, 34))
        draw.text((860, y + 70), state, fill=(80, 200, 120) if state == "active" else (160, 160, 100), font=font(FONT_SANS, 32))
        y += 240
    draw.text((80, y + 40), "SSH alias → home-pc", fill=(200, 200, 210), font=font(FONT_SANS, 36))
    img = add_noise(img, 5)
    img.save(path, quality=72)


def make_phone_screenshot_batcave_error(path: Path) -> None:
    w, h = 1170, 1800
    img = Image.new("RGB", (w, h), (250, 250, 252))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, w, 160], fill=(30, 30, 35))
    draw.text((60, 55), "Batcave", fill=(255, 255, 255), font=font(FONT_SANS_BOLD, 48))
    draw.rounded_rectangle([80, 280, w - 80, 720], radius=20, fill=(255, 235, 230))
    draw.text((120, 340), "D1 read limit exceeded", fill=(160, 30, 30), font=font(FONT_SANS_BOLD, 44))
    draw.text((120, 430), "Free tier daily reads exhausted.", fill=(60, 40, 40), font=font(FONT_SANS, 36))
    draw.text((120, 520), "Retry after reset or cache queries.", fill=(60, 40, 40), font=font(FONT_SANS, 36))
    draw.text((120, 620), "code: D1_ERROR_RATE_LIMIT", fill=(100, 60, 60), font=font(FONT_MONO, 28))
    draw.text((80, 820), "Overview", fill=(20, 20, 20), font=font(FONT_SANS_BOLD, 40))
    draw.text((80, 900), "Habits  — failed to load", fill=(120, 120, 120), font=font(FONT_SANS, 36))
    draw.text((80, 980), "Budget  — stale (cached)", fill=(120, 120, 120), font=font(FONT_SANS, 36))
    img = ImageEnhance.Contrast(img).enhance(0.98)
    img = add_noise(img, 3)
    img.save(path, quality=68)


def make_scanned_pdf(path: Path) -> None:
    """Two-page 'phone scan' PDF about homelab / Tailscale."""
    pages: list[Image.Image] = []
    for page_i, lines in enumerate(
        [
            [
                "Homelab runbook (scan)",
                "",
                "Box: headless Ubuntu on home-pc",
                "Reachability: Tailscale + MagicDNS",
                "Services: cron, usage server, tmux agents",
                "",
                "Setup checklist",
                "1. install Tailscale",
                "2. tailscale up",
                "3. enable MagicDNS",
                "4. SSH Host home-pc -> 100.x",
                "",
                "See also: Homelab Server note",
            ],
            [
                "Notes from last weekend",
                "",
                "- moved long agent jobs into tmux",
                "- usage server scrapes every 15m",
                "- don't expose ports; Tailscale only",
                "",
                "Open item: document exit nodes",
                "Link from Homelab Server -> Tailscale Setup",
            ],
        ]
    ):
        sheet = paper_bg((1275, 1650), (252, 250, 240))
        draw = ImageDraw.Draw(sheet)
        y = 100
        for j, line in enumerate(lines):
            fnt = font(FONT_SANS_BOLD if j == 0 else FONT_SANS, 48 if j == 0 else 36)
            draw.text((100, y), line, fill=(30, 30, 30), font=fnt)
            y += 70 if j == 0 else 58
        # Scan artifacts: skew, blur, shadow, contrast crush
        sheet = sheet.rotate(1.5 - page_i * 0.8, expand=True, fillcolor=(60, 60, 60))
        sheet = skew_perspective(sheet, 0.035 + 0.01 * page_i)
        # Dark scanner bed around edges
        sheet = ImageOps.expand(sheet, border=40, fill=(50, 50, 52))
        sheet = sheet.filter(ImageFilter.GaussianBlur(1.2))
        sheet = ImageEnhance.Contrast(sheet).enhance(1.25)
        sheet = ImageEnhance.Brightness(sheet).enhance(0.93)
        sheet = add_noise(sheet, 18)
        pages.append(sheet.convert("RGB"))

    pages[0].save(
        path,
        "PDF",
        resolution=150.0,
        save_all=True,
        append_images=pages[1:],
    )


def main() -> None:
    np.random.seed(0)
    make_voice(
        ROOT / "01_voice_gd_momentum.wav",
        "Quick memo for EECE 448. Learning rate too high and gradient descent diverges. "
        "Momentum helps smooth noisy gradients. I should update the Gradient Descent Notes "
        "and maybe link Adam from there.",
        seed=1,
    )
    make_whiteboard_regularization(ROOT / "02_whiteboard_regularization.jpg")
    make_handwritten_interview(ROOT / "03_handwritten_interview_prep.jpg")
    make_phone_screenshot_jobs(ROOT / "04_screenshot_job_pipeline.jpg")
    make_scanned_pdf(ROOT / "05_scanned_homelab.pdf")
    make_whiteboard_batcave(ROOT / "06_whiteboard_batcave_cache.jpg")
    make_voice(
        ROOT / "07_voice_weekly_review.wav",
        "Sunday review. Clear the inbox, check Job Search Pipeline follow-ups, "
        "plan the week around the machine learning lab, and look at Batcave Dashboard tasks.",
        seed=2,
    )
    make_phone_screenshot_tailscale(ROOT / "08_screenshot_tailscale.jpg")
    make_handwritten_study(ROOT / "09_handwritten_study_session.jpg")
    make_phone_screenshot_batcave_error(ROOT / "10_screenshot_batcave_error.jpg")
    print("Wrote captures to", ROOT)


if __name__ == "__main__":
    main()
