"""Assemble the 1-minute demo video from live recordings, animated cards and voice-over."""
import json, subprocess, sys
V = "/home/ralph/Code/demo-video"
W, H, X = 1920, 1080, 0.6          # frame size, crossfade length (s)

def ease(z0, z1, ta, tb):
    p = f"clip((t-{ta})/({tb}-{ta}),0,1)"
    return f"({z0}+({z1}-{z0})*{p}*{p}*(3-2*{p}))"

def zoom(z0, z1, c0, c1, ta, tb):
    """Eased zoom + pan with a fixed frame size (zoompan, time = output frame / 30).
    Input is upscaled 2x first so the pan stays smooth instead of stepping by whole pixels."""
    T = "(on/30)"
    e = lambda a, b: ease(a, b, ta, tb).replace("t-", T + "-")
    z = e(z0, z1)
    cx, cy = e(c0[0] * 2, c1[0] * 2), e(c0[1] * 2, c1[1] * 2)
    return (f"scale={2*W}:{2*H}:flags=lanczos,"
            f"zoompan=z='{z}':x='clip({cx}-iw/zoom/2,0,iw-iw/zoom)':y='clip({cy}-ih/zoom/2,0,ih-ih/zoom)'"
            f":d=1:s={W}x{H}:fps=30")


MID = (W/2, H/2)
ROUTE = (1690, 330)      # right-panel Route card
PANEL = (1690, 420)
VERIFY = (1690, 600)
# (source, start, end, output duration, zoom filter, voice line, transition into next)
SCENES = [
    ("raw/card_hook.webm",    0.3,  7.3, 7.0, None,                                          "h1", "fade"),
    ("raw/card_lossy.webm",   0.3,  7.8, 7.5, None,                                          "h2", "fadeblack"),
    ("raw/card_title.webm",   0.3,  6.3, 6.0, None,                                          "h3", "fade"),
    ("raw/confident.webm",    6.5, 15.5, 6.0, zoom(1, 1.15, MID, (1250, 450), 0, 6),          "h4", "slideleft"),
    ("raw/ambiguous.webm",   17.0, 33.0, 8.0, zoom(2.1, 1, ROUTE, MID, 2.6, 5.0),             "h5", "fade"),
    ("raw/ambiguous.webm",   31.5, 36.6, 4.5, zoom(1, 1.9, MID, VERIFY, 0.2, 2.2),            "h6", "fadeblack"),
    ("raw/card_twoai.webm",   0.3,  9.3, 9.0, None,                                          "h7", "fade"),
    ("raw/card_results.webm", 0.3, 11.8, 11.5, None,                                         "h8", "fade"),
    ("raw/card_end.webm",     0.3,  5.3, 5.0, None,                                          "h9", None),
]
args, fc, starts, t = [], [], [], 0.0
for i, (src, a, b, d, zf, *_ ) in enumerate(SCENES):
    args += ["-i", f"{V}/{src}"]
    speed = (b - a) / d
    f = f"[{i}:v]trim={a}:{b},setpts=(PTS-STARTPTS)/{speed:.4f},fps=30,scale={W}:{H}"
    if zf: f += "," + zf
    fc.append(f + f",settb=1/30,format=yuv420p[v{i}]")
    starts.append(t); t += d - X
total = t + X
cur = "v0"; off = 0
for i in range(1, len(SCENES)):
    off += SCENES[i-1][3] - X
    fc.append(f"[{cur}][v{i}]xfade=transition={SCENES[i-1][6]}:duration={X}:offset={off:.3f}[x{i}]")
    cur = f"x{i}"
# voice-over: each line starts 0.35 s into its scene
n = len(SCENES)
for i, s in enumerate(SCENES):
    args += ["-i", f"{V}/vo/f_{s[5]}.wav"]
    ms = int((starts[i] + 0.35) * 1000)
    fc.append(f"[{n+i}:a]aresample=48000,adelay={ms}|{ms},apad[a{i}]")
fc.append("".join(f"[a{i}]" for i in range(n)) + f"amix=inputs={n}:normalize=0,atrim=0:{total:.3f},afade=t=out:st={total-0.8:.3f}:d=0.8[aout]")
fc.append(f"[{cur}]fade=t=in:st=0:d=0.4,fade=t=out:st={total-0.6:.3f}:d=0.6[vout]")
out = sys.argv[1] if len(sys.argv) > 1 else f"{V}/capture-to-vault-demo-v2.mp4"
cmd = ["ffmpeg", "-loglevel", "error", "-y", *args, "-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "[aout]",
       "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
       "-movflags", "+faststart", out]
subprocess.run(cmd, check=True)
print(out, f"{total:.1f}s", "scene starts:", [round(s, 1) for s in starts])
