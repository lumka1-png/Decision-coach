"""Generates an original, royalty-free background track for the demo video.

Calm and optimistic: D major, 76 BPM, I-V-vi-IV progression with a warm pad,
an electric-piano arpeggio, soft bass and light percussion. Layers enter with
the video's sections and the track fades out at the end.

Usage: python3 music.py OUT.wav DURATION_SECONDS [--bpm N] [--arp-in S] [--bass-in S]
       [--perc-in S] [--perc-out S] [--peak-db DB] [--fade-in S] [--claps]
"""
import argparse
import wave

import numpy as np

SR = 44100
BPM = 76
BEAT = 60 / BPM
BAR = 4 * BEAT

# Section start times in the video (seconds).
ARP_IN, BASS_IN, PERC_IN, PERC_OUT = 5.5, 10.5, 24.5, 112.5
PEAK_DB, FADE_IN, CLAPS = -10.0, 2.0, False

# I - V - vi - IV in D major, as MIDI notes (root, third, fifth).
CHORDS = [(50, 54, 57), (57, 61, 64), (59, 62, 66), (55, 59, 62)]


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def env_ar(n, attack, release):
    e = np.ones(n)
    a, r = int(attack * SR), int(release * SR)
    e[:a] = np.linspace(0, 1, a)
    e[n - r:] *= np.linspace(1, 0, r)
    return e


def add(buf, start, sig, pan=0.0):
    i = int(start * SR)
    j = min(i + len(sig), buf.shape[1])
    if i >= buf.shape[1]:
        return
    left, right = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    buf[0, i:j] += sig[: j - i] * left
    buf[1, i:j] += sig[: j - i] * right


def pad_chord(chord, length):
    n = int(length * SR)
    t = np.arange(n) / SR
    sig = np.zeros(n)
    for note in chord:
        f = hz(note + 12)
        for cents in (-4, 4):
            sig += np.sin(2 * np.pi * f * 2 ** (cents / 1200) * t)
        sig += 0.25 * np.sin(2 * np.pi * f * 2 * t)
    sig *= 1 + 0.08 * np.sin(2 * np.pi * 0.25 * t)
    return sig * env_ar(n, 0.9, 1.2) / 8


def epiano(note, vel):
    n = int(1.6 * SR)
    t = np.arange(n) / SR
    f = hz(note)
    sig = np.zeros(n)
    for k, (amp, tau) in enumerate([(1.0, 0.7), (0.35, 0.35), (0.12, 0.2), (0.05, 0.12)], start=1):
        sig += amp * np.sin(2 * np.pi * f * k * t) * np.exp(-t / tau)
    sig *= np.minimum(1, t / 0.004)
    return sig * vel


def bass(note, length):
    n = int(length * SR)
    t = np.arange(n) / SR
    f = hz(note - 12)
    sig = np.sin(2 * np.pi * f * t) + 0.2 * np.sin(2 * np.pi * 2 * f * t)
    return sig * env_ar(n, 0.03, 0.4) * np.exp(-t / 2.5)


def kick():
    n = int(0.4 * SR)
    t = np.arange(n) / SR
    freq = 50 + 70 * np.exp(-t / 0.04)
    return np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-t / 0.12)


def shaker(rng):
    n = int(0.12 * SR)
    t = np.arange(n) / SR
    noise = rng.standard_normal(n)
    noise = np.diff(noise, prepend=0)  # tilt toward highs
    return noise * np.exp(-t / 0.03)


def clap(rng):
    n = int(0.18 * SR)
    t = np.arange(n) / SR
    noise = np.diff(rng.standard_normal(n), prepend=0)
    return noise * (np.exp(-t / 0.05) + 0.5 * np.exp(-((t - 0.012) ** 2) / 1e-5))


def reverb(buf, rng, seconds=2.6):
    n = int(seconds * SR)
    t = np.arange(n) / SR
    out = np.zeros_like(buf)
    size = 1 << int(np.ceil(np.log2(buf.shape[1] + n)))
    for ch in range(2):
        ir = rng.standard_normal(n) * np.exp(-t / 0.75)
        ir[: int(0.02 * SR)] = 0
        wet = np.fft.irfft(np.fft.rfft(buf[ch], size) * np.fft.rfft(ir, size), size)[: buf.shape[1]]
        out[ch] = wet / np.max(np.abs(ir)) / 60
    return out


def main(path, duration):
    rng = np.random.default_rng(7)
    total = int((duration + 3) * SR)
    pad = np.zeros((2, total))
    keys = np.zeros((2, total))
    low = np.zeros((2, total))
    perc = np.zeros((2, total))

    bar = 0
    while bar * BAR < duration:
        start = bar * BAR
        chord = CHORDS[bar % 4]
        add(pad, start, pad_chord(chord, BAR + 1.2))

        if start + BAR > ARP_IN:
            pattern = [0, 1, 2, 3, 2, 1, 2, 3]
            tones = [chord[0] + 12, chord[1] + 12, chord[2] + 12, chord[0] + 24]
            for k, idx in enumerate(pattern):
                at = start + k * BEAT / 2
                if at < ARP_IN:
                    continue
                vel = (0.32 if k % 2 == 0 else 0.22) * (0.9 + 0.2 * rng.random())
                add(keys, at, epiano(tones[idx], vel), pan=0.25 if k % 2 else -0.25)

        if start >= BASS_IN - BAR:
            for half in range(2):
                at = start + half * 2 * BEAT
                if at >= BASS_IN:
                    add(low, at, bass(chord[0], 2 * BEAT) * 0.5)

        for beat in range(4):
            at = start + beat * BEAT
            if PERC_IN <= at < PERC_OUT:
                if beat in (0, 2):
                    add(perc, at, kick() * 0.35)
                elif CLAPS:
                    add(perc, at, clap(rng) * 0.06)
                add(perc, at + BEAT / 2, shaker(rng) * 0.05, pan=0.3)
        bar += 1

    dry = pad * 0.55 + keys * 0.5 + low * 0.6 + perc
    mix = dry + reverb(pad * 0.55 + keys * 0.5, rng)
    mix = mix[:, : int(duration * SR)]

    n = mix.shape[1]
    fade = np.ones(n)
    fi, fo = int(FADE_IN * SR), int(min(4.0, duration / 8) * SR)
    fade[:fi] = np.linspace(0, 1, fi)
    fade[n - fo:] = np.linspace(1, 0, fo)
    mix *= fade
    mix *= 10 ** (PEAK_DB / 20) / np.max(np.abs(mix))

    pcm = (mix.T * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("duration", type=float)
    ap.add_argument("--bpm", type=float, default=BPM)
    ap.add_argument("--arp-in", type=float, default=ARP_IN)
    ap.add_argument("--bass-in", type=float, default=BASS_IN)
    ap.add_argument("--perc-in", type=float, default=PERC_IN)
    ap.add_argument("--perc-out", type=float, default=PERC_OUT)
    ap.add_argument("--peak-db", type=float, default=PEAK_DB, help="peak level; -10 is a quiet bed")
    ap.add_argument("--fade-in", type=float, default=FADE_IN)
    ap.add_argument("--claps", action="store_true", help="add claps on beats 2 and 4")
    a = ap.parse_args()
    BPM, BEAT, BAR = a.bpm, 60 / a.bpm, 240 / a.bpm
    ARP_IN, BASS_IN, PERC_IN, PERC_OUT = a.arp_in, a.bass_in, a.perc_in, a.perc_out
    PEAK_DB, FADE_IN, CLAPS = a.peak_db, a.fade_in, a.claps
    main(a.out, a.duration)
