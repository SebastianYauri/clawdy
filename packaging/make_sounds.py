#!/usr/bin/env python3
"""Generates Clawdy's 8-bit sounds (square waves, like old consoles) into assets/."""
import math
import os
import struct
import wave

RATE = 22050
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")


def square(freq, secs, vol=0.35, duty=0.5, slide=0.0):
    out = []
    n = int(RATE * secs)
    phase = 0.0
    for i in range(n):
        f = freq * (1 + slide * i / n)
        phase = (phase + f / RATE) % 1.0
        env = min(1.0, i / (RATE * 0.004)) * min(1.0, (n - i) / (RATE * 0.012))   # no clicks
        out.append((1 if phase < duty else -1) * vol * env)
    return out


def rest(secs):
    return [0.0] * int(RATE * secs)


def save(name, samples):
    with wave.open(os.path.join(ROOT, name), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, s)) * 32767)) for s in samples))


# "bip-bip-biiip": a classic low-health warning
save("alert.wav", square(880, 0.08, duty=0.25) + rest(0.04) + square(880, 0.08, duty=0.25) + rest(0.04)
     + square(1318.5, 0.22, duty=0.25, slide=-0.08))
