#!/usr/bin/env python3
"""Generate synthetic, unprepared-looking demo captures for mock_vault.

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


def add_noise(img: Image.Image, sigma: float = 12.0, seed: int = 42) -> Image.Image:
    arr = np.asarray(img).astype(np.float32)
    noise = np.random.default_rng(seed).normal(0, sigma, arr.shape)
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
    with tempfile.TemporaryDirectory() as td:
        clean = Path(td) / "clean.wav"
        noisy = Path(td) / "noisy.wav"
        subprocess.run(
            ["espeak-ng", "-v", "en-us", "-s", "155", "-p", "45", "-w", str(clean), text],
            check=True,
        )
        af = (
            f"anoisesrc=color=pink:sample_rate=22050:duration=30:amplitude=0.02:seed={seed}[n];"
            f"[0:a][n]amix=inputs=2:duration=first:dropout_transition=0,"
            f"highpass=f=120,lowpass=f=3800,volume=1.1"
        )
        proc = subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(clean),
                "-filter_complex", af, "-ar", "22050", "-ac", "1", str(noisy),
            ],
            capture_output=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.decode()[-800:])
        path.write_bytes(noisy.read_bytes())


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
    for ch in text:
        oy = int(rng.integers(-2, 3))
        ox = int(rng.integers(-1, 2))
        draw.text((x + ox, y + oy), ch, fill=fill, font=fnt)
        bbox = draw.textbbox((0, 0), ch, font=fnt)
        x += bbox[2] - bbox[0] + int(rng.integers(0, 2))


def finish_photo(img: Image.Image, path: Path, blur: float = 1.2, sigma: float = 10, strength: float = 0.045) -> None:
    img = skew_perspective(img, strength)
    img = img.filter(ImageFilter.GaussianBlur(radius=blur))
    img = add_noise(img, sigma)
    img = ImageEnhance.Contrast(img).enhance(0.94)
    img.convert("RGB").save(path, quality=78, optimize=True)


# --- individual captures -------------------------------------------------


def make_01_voice_eece448(path: Path) -> None:
    make_voice(
        path,
        "EECE 448 memo. Ridge versus lasso on the housing set — L2 shrinks weights, "
        "L1 drives some to zero. Tie this back to gradient descent step size and the "
        "regularization notes for class.",
        seed=11,
    )


def make_02_whiteboard_smith(path: Path) -> None:
    img = Image.new("RGB", (1400, 1000), (240, 244, 248))
    draw = ImageDraw.Draw(img)
    draw.rectangle([40, 40, 1360, 920], fill=(252, 253, 255), outline=(80, 80, 85), width=6)
    draw.rectangle([40, 920, 1360, 960], fill=(65, 65, 70))
    draw.text((120, 80), "PHYS 230 — Smith chart", fill=(20, 50, 120), font=font(FONT_SANS_BOLD, 52))
    # crude smith-chart circle
    draw.ellipse([780, 200, 1180, 600], outline=(30, 30, 30), width=3)
    draw.ellipse([880, 300, 1080, 500], outline=(30, 90, 160), width=2)
    draw.line([(780, 400), (1180, 400)], fill=(30, 30, 30), width=2)
    draw.text((820, 620), "z = 0.4 + j0.7", fill=(160, 40, 40), font=font(FONT_SANS_BOLD, 36))
    lines = [
        "toward generator → CW",
        "toward load → CCW",
        "match with series L then shunt C",
        "check VSWR circle first",
        "",
        "HW: practice set #3",
    ]
    y = 200
    for line in lines:
        jitter = int(3 * math.sin(y / 35))
        draw.text((110 + jitter, y), line, fill=(25, 25, 25), font=font(FONT_SANS, 38))
        y += 75
    finish_photo(img, path, blur=1.5, sigma=9, strength=0.05)


def make_03_handwritten_anchoring(path: Path) -> None:
    img = paper_bg((1100, 1400))
    draw = ImageDraw.Draw(img)
    _wobbly_text(draw, (90, 70), "ECON 205 — Anchoring", (25, 40, 90), font(FONT_SERIF, 42), 1)
    notes = [
        "Estimates drift toward the first number",
        "even if the number is irrelevant",
        "",
        "Demo: wheel of fortune → GDP guess",
        "Retail: 'was $80, now $49'",
        "",
        "vs loss aversion (separate note)",
        "Nudges can set the anchor on purpose",
        "",
        "Read: Kahneman ch. on anchors",
    ]
    y = 170
    for i, line in enumerate(notes):
        _wobbly_text(draw, (100, y), line, (30, 30, 30), font(FONT_SERIF, 34), 10 + i)
        y += 95
    draw.ellipse([820, 1120, 980, 1280], outline=(190, 160, 120), width=3)
    img = img.rotate(2.0, expand=True, fillcolor=(248, 244, 230))
    finish_photo(img, path, blur=0.9, sigma=14, strength=0.03)


def make_04_screenshot_job_search(path: Path) -> None:
    w, h = 1170, 2400
    img = Image.new("RGB", (w, h), (245, 245, 247))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, w, 90], fill=(245, 245, 247))
    draw.text((60, 28), "9:41", fill=(0, 0, 0), font=font(FONT_SANS_BOLD, 36))
    draw.text((900, 28), "LTE  71%", fill=(0, 0, 0), font=font(FONT_SANS, 32))
    draw.rectangle([0, 90, w, 260], fill=(25, 70, 150))
    draw.text((60, 145), "Job Search", fill=(255, 255, 255), font=font(FONT_SANS_BOLD, 60))
    rows = [
        ("Embedded ML — ChipCo", "Screen", (40, 140, 80)),
        ("Firmware intern — EdgeNet", "Applied", (60, 100, 180)),
        ("Systems SWE — CloudForge", "Found", (120, 120, 120)),
        ("On-device inference — GPU Labs", "Technical", (180, 100, 30)),
    ]
    y = 300
    for title, stage, color in rows:
        draw.rounded_rectangle([48, y, w - 48, y + 210], radius=28, fill=(255, 255, 255))
        draw.text((90, y + 40), title, fill=(20, 20, 20), font=font(FONT_SANS_BOLD, 38))
        draw.rounded_rectangle([90, y + 115, 90 + 260, y + 175], radius=16, fill=color)
        draw.text((120, y + 128), stage, fill=(255, 255, 255), font=font(FONT_SANS_BOLD, 30))
        y += 240
    draw.text((80, y + 20), "Prep: system design mock Thu", fill=(60, 60, 70), font=font(FONT_SANS, 34))
    img = ImageEnhance.Color(img).enhance(0.95)
    img = add_noise(img, 4, seed=4)
    img.save(path, quality=72, optimize=True)


def make_05_scanned_homelab(path: Path) -> None:
    pages: list[Image.Image] = []
    blocks = [
        [
            "Homelab runbook (phone scan)",
            "",
            "Box: headless Ubuntu",
            "Reachability: Tailscale + MagicDNS",
            "Long jobs: tmux sessions (survive SSH drop)",
            "Cron: moved off laptop Nov 14",
            "",
            "Checklist",
            "1. tailscale up",
            "2. tmux new -s agents",
            "3. ACL: only home devices",
            "",
            "Project note: Homelab Server",
        ],
        [
            "Follow-ups",
            "",
            "- document exit nodes",
            "- ACL cleanup after Nov 20 session",
            "- keep cron on the box, not laptop",
            "",
            "Concepts: Tailscale, tmux, Cron jobs",
        ],
    ]
    for page_i, lines in enumerate(blocks):
        sheet = paper_bg((1275, 1650), (252, 250, 240))
        draw = ImageDraw.Draw(sheet)
        y = 100
        for j, line in enumerate(lines):
            fnt = font(FONT_SANS_BOLD if j == 0 else FONT_SANS, 48 if j == 0 else 36)
            draw.text((100, y), line, fill=(30, 30, 30), font=fnt)
            y += 70 if j == 0 else 58
        sheet = sheet.rotate(1.4 - page_i * 0.7, expand=True, fillcolor=(60, 60, 60))
        sheet = skew_perspective(sheet, 0.035 + 0.01 * page_i)
        sheet = ImageOps.expand(sheet, border=40, fill=(50, 50, 52))
        sheet = sheet.filter(ImageFilter.GaussianBlur(1.2))
        sheet = ImageEnhance.Contrast(sheet).enhance(1.2)
        sheet = add_noise(sheet, 18, seed=50 + page_i)
        pages.append(sheet.convert("RGB"))
    pages[0].save(path, "PDF", resolution=150.0, save_all=True, append_images=pages[1:])


def make_06_whiteboard_plant_bot(path: Path) -> None:
    img = Image.new("RGB", (1280, 900), (236, 240, 244))
    draw = ImageDraw.Draw(img)
    draw.rectangle([30, 30, 1250, 850], fill=(250, 252, 255), outline=(60, 60, 65), width=5)
    draw.text((90, 60), "Plant Watering Bot — ESP32", fill=(20, 20, 20), font=font(FONT_SANS_BOLD, 46))
    # block diagram
    boxes = [(100, 200, "soil probe"), (420, 200, "ESP32 ADC"), (740, 200, "MQTT"), (1000, 200, "valve")]
    for x, y, label in boxes:
        draw.rounded_rectangle([x, y, x + 200, y + 110], radius=12, outline=(30, 30, 30), width=3)
        draw.text((x + 20, y + 35), label, fill=(30, 30, 30), font=font(FONT_SANS, 28))
    draw.line([(300, 255), (420, 255)], fill=(30, 30, 30), width=3)
    draw.line([(620, 255), (740, 255)], fill=(30, 30, 30), width=3)
    draw.line([(940, 255), (1000, 255)], fill=(30, 30, 30), width=3)
    bullets = [
        "capacitive moisture → ADC",
        "publish dry/wet over MQTT",
        "threshold opens relay / valve",
        "next: calibrate dry vs saturated",
    ]
    y = 400
    for line in bullets:
        draw.text((120, y), "•  " + line, fill=(35, 35, 40), font=font(FONT_SANS, 34))
        y += 70
    finish_photo(img, path, blur=1.4, sigma=10, strength=0.055)


def make_07_voice_homelab(path: Path) -> None:
    make_voice(
        path,
        "Homelab note. Moved the long agent jobs into a tmux session on the Ubuntu box "
        "so SSH drops do not kill them. Tailscale MagicDNS still reaches home-pc. "
        "Update the Homelab Server project.",
        seed=22,
    )


def make_08_merge_soil_followup(path: Path) -> None:
    """Clear continuation of Plant Watering Bot soil calibration — should MERGE."""
    img = paper_bg((1000, 1280), (250, 247, 235))
    draw = ImageDraw.Draw(img)
    _wobbly_text(draw, (80, 60), "Plant Watering Bot — follow-up", (40, 40, 40), font(FONT_SERIF, 38), 3)
    lines = [
        "Same soil sensor as Nov 12 calib session",
        "More points (still ESP32 ADC):",
        "  air/dry  = 820",
        "  damp     = 540",
        "  saturated= 310",
        "",
        "Merge into Plant Watering Bot note",
        "(or the Calibrated soil sensor session)",
        "Threshold draft: water below 480",
    ]
    y = 160
    for i, line in enumerate(lines):
        _wobbly_text(draw, (90, y), line, (25, 25, 25), font(FONT_SERIF, 32), 20 + i)
        y += 90
    img = img.rotate(-1.5, expand=True, fillcolor=(250, 247, 235))
    finish_photo(img, path, blur=1.0, sigma=15, strength=0.035)


def make_09_ambiguous_cross_domain(path: Path) -> None:
    """Intentionally straddles Job Search + ECON anchoring + EECE bias — low confidence."""
    img = paper_bg((1100, 1350), (252, 248, 238))
    draw = ImageDraw.Draw(img)
    _wobbly_text(draw, (80, 60), "coffee dump — where does this go?", (90, 40, 40), font(FONT_SERIF, 36), 5)
    lines = [
        "First offer number anchors the whole",
        "salary negotiation — classic anchoring",
        "(ECON 205?) but it's for an ML role",
        "so maybe Job Search / Interview Prep",
        "",
        "Also: recruiter 'range' feels like a nudge",
        "",
        "Side thought: bias-variance on the",
        "take-home model — am I overfitting",
        "the practice set? EECE 448??",
        "",
        "ugh file this somewhere",
    ]
    y = 160
    for i, line in enumerate(lines):
        _wobbly_text(draw, (90, y), line, (30, 30, 30), font(FONT_SERIF, 32), 40 + i)
        y += 85
    img = img.rotate(1.2, expand=True, fillcolor=(252, 248, 238))
    finish_photo(img, path, blur=1.1, sigma=16, strength=0.04)


def make_10_screenshot_interview(path: Path) -> None:
    w, h = 1170, 1800
    img = Image.new("RGB", (w, h), (18, 18, 22))
    draw = ImageDraw.Draw(img)
    draw.text((60, 40), "9:41", fill=(230, 230, 230), font=font(FONT_SANS_BOLD, 34))
    draw.text((80, 140), "Mock interview notes", fill=(255, 255, 255), font=font(FONT_SANS_BOLD, 52))
    draw.text((80, 230), "System design — rate limiter", fill=(160, 200, 255), font=font(FONT_SANS, 36))
    bullets = [
        "token bucket vs leaky bucket",
        "redis counters per API key",
        "edge vs central enforce",
        "tie to Interview Prep note",
        "Job Search: ChipCo screen Thu",
    ]
    y = 340
    for b in bullets:
        draw.rounded_rectangle([60, y, w - 60, y + 120], radius=18, fill=(40, 40, 48))
        draw.text((100, y + 35), b, fill=(235, 235, 240), font=font(FONT_SANS, 34))
        y += 150
    img = add_noise(img, 5, seed=10)
    img.save(path, quality=72, optimize=True)


def main() -> None:
    # Remove prior-generation media so renames do not leave orphans.
    for p in ROOT.iterdir():
        if p.suffix.lower() in {".wav", ".jpg", ".jpeg", ".png", ".pdf", ".m4a", ".mp3"}:
            p.unlink()

    make_01_voice_eece448(ROOT / "01_voice_eece448_ridge.wav")
    make_02_whiteboard_smith(ROOT / "02_whiteboard_smith_chart.jpg")
    make_03_handwritten_anchoring(ROOT / "03_handwritten_anchoring.jpg")
    make_04_screenshot_job_search(ROOT / "04_screenshot_job_search.jpg")
    make_05_scanned_homelab(ROOT / "05_scanned_homelab_tmux.pdf")
    make_06_whiteboard_plant_bot(ROOT / "06_whiteboard_plant_bot_esp32.jpg")
    make_07_voice_homelab(ROOT / "07_voice_homelab_tmux.wav")
    make_08_merge_soil_followup(ROOT / "08_merge_soil_sensor_followup.jpg")
    make_09_ambiguous_cross_domain(ROOT / "09_ambiguous_salary_anchor.jpg")
    make_10_screenshot_interview(ROOT / "10_screenshot_interview_prep.jpg")
    print("Wrote captures to", ROOT)


if __name__ == "__main__":
    main()
