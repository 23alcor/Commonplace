"""Build demo_captures/11_video_study_and_plant_bot.mp4 (lane A video test input; no personal data).

A ~4 min narrated work-session recording that spans two projects: EECE 448 (ridge regression,
cross-validation, bias-variance) then the Plant Watering Bot (ESP32, soil calibration, MQTT).
Deliberate test content:
  * on-screen only facts (CV results table, code) the narrator never reads out
  * a spoken correction that overrides what's on screen (threshold 480 -> 650): a decision
  * action items spread across the video, gathered again at the end

    python demo_captures/make_11_video.py      # needs GEMINI_API_KEY (TTS), Pillow, ffmpeg
"""
from __future__ import annotations

import base64
import io
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from c2v.config import MODEL_IDS  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "11_video_study_and_plant_bot.mp4"
W, H = 1280, 720
SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
PAD_S = 2.5  # pause after each narration line (time to read the screen)

SEGMENTS = [
    ("slide", {"title": "Saturday work session", "lines": [
        "1. EECE 448 - HW5: ridge regression", "    closed form, pick lambda with CV",
        "2. Plant Watering Bot", "    soil threshold, MQTT loop"]},
     "Okay, recording this so I don't lose it. Saturday work session. Two things today. First, the "
     "EECE 448 homework five on ridge regression. Then the plant watering bot, where I want to lock down "
     "the soil sensor threshold and the M Q T T loop."),
    ("slide", {"title": "Ridge regression", "lines": [
        "L(w) = ||y - Xw||^2 + lambda ||w||^2", "", "w* = (X^T X + lambda I)^-1 X^T y", "",
        "+ lambda I fixes near-singular X^T X", "  (correlated features: housing data)"]},
     "So, ridge. The loss is the usual squared error plus lambda times the squared norm of the weights. "
     "The closed form just adds lambda times the identity before inverting X transpose X, which also "
     "fixes the matrix being near singular when features are correlated. That's exactly the housing data "
     "problem from last week's ridge versus lasso session."),
    ("code", {"title": "hw5_ridge.py", "code": [
        "alphas = np.logspace(-1, 1.5, 6)",
        "model = RidgeCV(alphas=alphas, cv=5,",
        "                scoring='neg_root_mean_squared_error')",
        "model.fit(X_train, y_train)", "",
        "#  alpha    CV RMSE",
        "#   0.10    41,210",
        "#   0.32    39,870",
        "#   1.00    38,940",
        "#   3.16    37,620   <- best",
        "#  10.00    38,110",
        "#  31.62    40,730"]},
     "To pick lambda I'm using Ridge C V with five fold cross validation over a log spaced grid. The "
     "results are on screen. Decision: we go with alpha around three point two. It has the lowest "
     "validation error, and the curve is pretty flat around it, so it's not a fragile choice."),
    ("plot", {"title": "Validation curve (5-fold CV)"},
     "Here's the validation curve, so it's not just a table. Error on the y axis, log alpha on the x axis. "
     "Training error in blue goes up monotonically as alpha grows, validation in orange has that U shape "
     "with the bottom right around three. Past thirty it's clearly underfitting."),
    ("slide", {"title": "Bias-variance check", "lines": [
        "lambda up  ->  bias up, variance down", "train error creeps up, val error dips then rises", "",
        "? lasso zeroed out sqft_basement", "   ask at office hours (Tue)"]},
     "Quick bias variance sanity check. Bigger lambda means more bias and less variance, and you can see "
     "the training error creep up while validation dips and then rises again. One thing I don't get: "
     "lasso zeroed out the basement square footage feature completely. Action item: ask about that at "
     "office hours on Tuesday."),
    ("image", {"path": HERE / "06_whiteboard_plant_bot_esp32.jpg"},
     "Switching over to the plant watering bot. Here's the architecture from the whiteboard. A capacitive "
     "soil probe goes into the E S P thirty two A D C, we publish over M Q T T, and a threshold opens the "
     "relay for the valve."),
    ("image", {"path": HERE / "08_merge_soil_sensor_followup.jpg"},
     "Calibration follow up. Same sensor as the November twelfth calibration session, and the readings "
     "are on the notebook page. The draft threshold on the page says water below four eighty. Actually, "
     "that's backwards: higher readings are drier on this sensor. So the decision is: water when the "
     "reading goes above six fifty."),
    ("code", {"title": "plant_bot.ino", "code": [
        "const int SOIL_PIN = 34;",
        "const int DRY_THRESHOLD = 650;   // higher = drier",
        "",
        "void loop() {",
        "  int raw = analogRead(SOIL_PIN);",
        "  mqtt.publish(\"plants/basil/moisture\",",
        "               String(raw).c_str(), true);  // retain",
        "  if (raw > DRY_THRESHOLD) openValve(4000);",
        "  delay(60000);",
        "}"]},
     "Here's the loop. Read pin thirty four once a minute, publish the raw value to plants, slash basil, "
     "slash moisture, with the retain flag on so the dashboard gets the last value right away, and open "
     "the valve for four seconds when it's too dry."),
    ("slide", {"title": "MQTT topics", "lines": [
        "plants/basil/moisture     raw ADC, retained", "plants/basil/valve        cmd: open <ms>",
        "plants/tomato/moisture   (planned)", "", "valve cmds: QoS 1", "telemetry: QoS 0"]},
     "Topic layout, one subtree per plant. Moisture is retained telemetry, valve is a command topic that "
     "takes a duration in milliseconds. Decision: valve commands go out at Q o S one so they're delivered "
     "at least once, and plain telemetry stays at Q o S zero. The tomato topics are there for when the "
     "second sensor arrives."),
    ("slide", {"title": "TODO", "lines": [
        "[ ] HW5: submit by Thu night", "[ ] office hours: lasso + sqft_basement",
        "[ ] order 2nd capacitive sensor (tomato pot)", "[ ] max watering / day safety limit"]},
     "Wrapping up. To do: finish homework five and submit it by Thursday night. Ask about the lasso "
     "basement feature at office hours. Order a second capacitive sensor for the tomato pot. And add a "
     "maximum watering per day safety limit, so one bad reading can't flood the plant. That's it."),
]


def plot(spec: dict) -> Image.Image:
    im = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.text((70, 40), spec["title"], font=ImageFont.truetype(BOLD, 40), fill=(25, 40, 110))
    x0, y0, x1, y1 = 140, 620, 1180, 130
    d.line([(x0, y0), (x1, y0)], fill=0, width=2)
    d.line([(x0, y0), (x0, y1)], fill=0, width=2)
    small = ImageFont.truetype(SANS, 22)
    d.text((x1 - 120, y0 + 15), "log10(alpha)", font=small, fill=0)
    d.text((40, y1 - 40), "RMSE ($k)", font=small, fill=0)
    xs = [i / 40 for i in range(41)]  # 0..1 over log alpha -1..1.5

    def px(u, v):  # v in $k between 30 and 45
        return x0 + u * (x1 - x0), y0 - (v - 30) / 15 * (y0 - y1)

    train = [px(u, 31 + 7 * u ** 1.6) for u in xs]
    val = [px(u, 37.6 + 14 * (u - 0.6) ** 2 + (3.5 * (u - 0.6) ** 2 if u > 0.6 else 0)) for u in xs]
    d.line(train, fill=(40, 90, 200), width=4)
    d.line(val, fill=(235, 130, 30), width=4)
    bx, by = px(0.6, 37.6)
    d.ellipse([bx - 8, by - 8, bx + 8, by + 8], outline=(200, 30, 30), width=3)
    d.text((bx + 14, by + 8), "alpha = 3.16", font=small, fill=(200, 30, 30))
    for u, lab in [(0, "-1"), (0.4, "0"), (0.8, "1"), (1.0, "1.5")]:
        d.text((px(u, 30)[0] - 10, y0 + 15), lab, font=small, fill=0)
    d.text((900, 150), "train", font=small, fill=(40, 90, 200))
    d.text((900, 180), "validation", font=small, fill=(235, 130, 30))
    return im


def render(kind: str, spec: dict) -> Image.Image:
    if kind == "plot":
        return plot(spec)
    if kind == "image":
        src = Image.open(spec["path"]).convert("RGB")
        src.thumbnail((W, H))
        bg = Image.new("RGB", (W, H), (24, 24, 24))
        bg.paste(src, ((W - src.width) // 2, (H - src.height) // 2))
        return bg
    dark = kind == "code"
    im = Image.new("RGB", (W, H), (30, 32, 38) if dark else (250, 250, 247))
    d = ImageDraw.Draw(im)
    d.text((70, 50), spec["title"], font=ImageFont.truetype(BOLD, 46),
           fill=(230, 230, 230) if dark else (25, 40, 110))
    lines = spec.get("code") or spec["lines"]
    font = ImageFont.truetype(MONO if dark else SANS, 30 if dark else 38)
    step = 44 if dark else 62
    for i, line in enumerate(lines):
        col = (130, 200, 130) if dark and line.lstrip().startswith(("#", "//")) else \
            (220, 220, 220) if dark else (30, 30, 30)
        d.text((80, 140 + i * step), line, font=font, fill=col)
    return im


def tts(text: str, client) -> bytes:
    r = client.interactions.create(model=MODEL_IDS["tts"], input=text, response_format={"type": "audio"},
                                   generation_config={"speech_config": [{"voice": "Puck"}]})
    data = r.output_audio.data
    return base64.b64decode(data) if isinstance(data, str) else data


def main() -> None:
    from google import genai

    client = genai.Client(http_options={"api_version": "v1beta"})
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        parts, t = [], 0.0
        for i, (kind, spec, text) in enumerate(SEGMENTS):
            render(kind, spec).save(tmp / f"s{i}.png")
            wav = tts(text, client)
            (tmp / f"s{i}.wav").write_bytes(wav)
            with wave.open(io.BytesIO(wav)) as w:
                dur = w.getnframes() / w.getframerate() + PAD_S
            print(f"[{int(t)//60:02d}:{int(t)%60:02d}] segment {i} {dur:.1f}s", flush=True)
            t += dur
            seg = tmp / f"s{i}.mp4"
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-loop", "1", "-framerate", "10",
                            "-i", str(tmp / f"s{i}.png"), "-i", str(tmp / f"s{i}.wav"),
                            "-af", f"apad=pad_dur={PAD_S}", "-t", f"{dur:.2f}",
                            "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p", "-crf", "28",
                            "-r", "10", "-c:a", "aac", "-b:a", "64k", "-ar", "24000", "-ac", "1", str(seg)],
                           check=True)
            parts.append(seg)
        (tmp / "list.txt").write_text("".join(f"file '{p}'\n" for p in parts))
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
                        "-i", str(tmp / "list.txt"), "-c", "copy", "-movflags", "+faststart", str(OUT)],
                       check=True)
    print(f"{OUT.name}: {t/60:.1f} min, {OUT.stat().st_size/1e6:.1f} MB")


if __name__ == "__main__":
    main()
