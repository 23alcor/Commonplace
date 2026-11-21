"""Create reproducible, local visual captures from held-out note prose."""
from __future__ import annotations

import io
import base64
import random
import re
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont
import numpy as np

from c2v.config import MODEL_IDS
from c2v.vault import split_frontmatter

KINDS = ("screenshot", "handwritten", "scanned_pdf")
DIFFICULTIES = ("clean", "noisy", "hard")


def capture_text(markdown: str) -> str:
    """Remove answer-bearing title/frontmatter/links, retaining readable prose."""
    _, body = split_frontmatter(markdown)
    body = re.sub(r"\[\[[^\]]+\]\]", "", body)
    body = re.sub(r"(?m)^\s*#{1,6}\s+.*$", "", body)
    return re.sub(r"\n{3,}", "\n\n", body).strip()


def prepare_text(markdown: str, difficulty: str, distractor: str = "") -> tuple[str, dict]:
    if difficulty not in DIFFICULTIES:
        raise ValueError(f"unknown difficulty: {difficulty}")
    text = capture_text(markdown)
    knobs = {"difficulty": difficulty, "partial_fraction": 1.0, "ambiguous_topic": False}
    if difficulty == "hard":
        cut = max(40, int(len(text) * 0.68))
        text = text[:cut].rsplit(" ", 1)[0].rstrip(" .,") + "... [rest obscured]"
        knobs["partial_fraction"] = 0.68
        extra = capture_text(distractor) if distractor else ""
        if extra:
            sentence = re.split(r"(?<=[.!?])\s+", extra)[0]
            text += "\n\nAlso on my mind: " + sentence[:150]
            knobs["ambiguous_topic"] = True
    return text, knobs


def _font(size: int, handwriting: bool = False):
    paths = (["/usr/share/fonts/truetype/liberation2/LiberationSerif-Italic.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf"] if handwriting else [])
    paths += ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    for path in paths:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _wrap(draw, text: str, font, width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines():
        line = ""
        for word in paragraph.split():
            candidate = f"{line} {word}".strip()
            if line and draw.textlength(candidate, font=font) > width:
                lines.append(line)
                line = word
            else:
                line = candidate
        lines.append(line)
    return lines


def render_image(markdown: str, out: Path, kind: str, seed: int = 42,
                 difficulty: str = "noisy", distractor: str = "") -> dict:
    if kind not in KINDS:
        raise ValueError(f"unsupported local visual kind: {kind}")
    rng = random.Random(seed)
    text, knobs = prepare_text(markdown, difficulty, distractor)
    if not text:
        raise ValueError("capture has no prose after removing title and links")
    handwritten = kind == "handwritten"
    width, margin = 960, 75
    font = _font(30 if handwritten else 26, handwritten)
    sizing = Image.new("RGB", (width, 100), "white")
    lines = _wrap(ImageDraw.Draw(sizing), text, font, width - 2 * margin)
    line_height = 54 if handwritten else 44
    height = max(640, 2 * margin + len(lines) * line_height)
    background = (246, 240, 222) if handwritten else (250, 250, 250)
    image = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(image)
    if kind == "screenshot":
        draw.rectangle((0, 0, width, 48), fill=(226, 229, 234))
        for x, color in ((20, "#ec6a5e"), (43, "#f4bf4f"), (66, "#61c454")):
            draw.ellipse((x, 17, x + 13, 30), fill=color)
    if handwritten:
        for y in range(margin, height, line_height):
            draw.line((40, y + 39, width - 40, y + 39), fill=(192, 205, 218), width=1)
    for i, line in enumerate(lines):
        jitter = rng.randint(-5, 5) if handwritten else 0
        draw.text((margin + jitter, margin + i * line_height), line, font=font,
                  fill=(44, 48, 71) if handwritten else (32, 32, 32))
    settings = {"clean": (0.5, 0.1, 0.25, 95, 0),
                "noisy": (5, 1.0, 2.0, 35, 8),
                "hard": (8, 2.8, 3.8, 20, 25)}
    max_rotate, min_blur, max_blur, jpeg_quality, pixel_noise = settings[difficulty]
    rotation = rng.uniform(-max_rotate, max_rotate)
    blur = round(rng.uniform(min_blur, max_blur), 2)
    image = image.rotate(rotation, resample=Image.Resampling.BICUBIC, expand=True,
                         fillcolor=background)
    if handwritten:
        w, h = image.size
        image = image.transform((w, h), Image.Transform.QUAD,
                                (18, 12, w - 22, 0, w - 2, h - 20, 0, h - 5),
                                resample=Image.Resampling.BICUBIC)
        shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rectangle((0, 0, w, h), outline=(30, 30, 30, 45), width=24)
        image = Image.alpha_composite(image.convert("RGBA"), shadow.filter(ImageFilter.GaussianBlur(22))).convert("RGB")
    image = image.filter(ImageFilter.GaussianBlur(blur))
    if pixel_noise:
        arr = np.asarray(image).astype(np.int16)
        arr += np.random.default_rng(seed).normal(0, pixel_noise, arr.shape).astype(np.int16)
        image = Image.fromarray(np.uint8(np.clip(arr, 0, 255)), "RGB")
    out.parent.mkdir(parents=True, exist_ok=True)
    if kind == "scanned_pdf":
        image.save(out, "PDF", resolution=150.0)
    else:
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=jpeg_quality)
        Image.open(buffer).convert("RGB").save(out, "PNG")
    return {**knobs, "rotation_deg": round(rotation, 2), "blur_px": blur,
            "pixel_noise_sd": pixel_noise,
            "jpeg_quality": jpeg_quality if kind != "scanned_pdf" else None}


def render_voice(markdown: str, out: Path, seed: int = 42, client=None,
                 difficulty: str = "noisy", distractor: str = "") -> dict:
    """Speak the substance conversationally, then mix reproducible room noise."""
    from google import genai

    text, knobs = prepare_text(markdown, difficulty, distractor)
    if not text:
        raise ValueError("capture has no prose")
    # Let the TTS model retell the substance instead of reading note prose verbatim.
    speech = ("Speak an informal first-person voice memo that paraphrases these points. "
              "Do not read them verbatim or mention a note title: " +
              re.sub(r"(?m)^[-*]\s*", "", text).replace("\n", ". "))
    client = client or genai.Client(http_options={"api_version": "v1beta"})
    response = client.interactions.create(
        model=MODEL_IDS["tts"], input=speech,
        response_format={"type": "audio"},
        generation_config={"speech_config": [{"voice": "Puck"}]})
    audio = response.output_audio
    if audio is None or audio.data is None:
        raise ValueError("TTS returned no audio")
    payload = base64.b64decode(audio.data) if isinstance(audio.data, str) else audio.data
    with wave.open(io.BytesIO(payload), "rb") as source:
        rate, channels, width = source.getframerate(), source.getnchannels(), source.getsampwidth()
        if width != 2:
            raise ValueError(f"TTS returned unsupported sample width: {width}")
        samples = np.frombuffer(source.readframes(source.getnframes()), dtype="<i2").astype(np.float32)
    rng = np.random.default_rng(seed)
    snr_ranges = {"clean": (20, 25), "noisy": (8, 13), "hard": (2, 5)}
    snr_db = random.Random(seed).uniform(*snr_ranges[difficulty])
    clean_rms = float(np.sqrt(np.mean(samples ** 2)))
    noise = rng.normal(0, 1, size=samples.shape).astype(np.float32)
    # Add low-frequency hum and a slow change in level for realistic room sound.
    t = np.arange(samples.size, dtype=np.float32) / (rate * channels)
    noise += 0.3 * np.sin(2 * np.pi * 60 * t)
    noise *= (0.7 + 0.3 * np.sin(2 * np.pi * 0.13 * t))
    noise *= clean_rms / (10 ** (snr_db / 20) * float(np.sqrt(np.mean(noise ** 2))))
    mixed = np.clip(samples + noise, -32768, 32767).astype("<i2")
    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as target:
        target.setnchannels(channels)
        target.setsampwidth(width)
        target.setframerate(rate)
        target.writeframes(mixed.tobytes())
    return {**knobs, "snr_db": round(snr_db, 2)}
