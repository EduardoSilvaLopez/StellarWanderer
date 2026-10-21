"""Generate the sound effects in common/resources/sounds (see common/audio.py).

Run from the project root:  python tools/generate_sounds.py

Simple electronic tones (metal clanks for the ore, a roar of air for arriving and leaving a world), made with numpy and
written as 16-bit mono WAV files: the sounds of a cockpit in vacuum, never of space. They are placeholders: any WAV of
the same name in that folder replaces one.
"""

import os
import wave
from typing import List, Tuple
import numpy as np

RATE = 22050
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'common', 'resources', 'sounds')


def tone(freq: float, seconds: float, loudness: float = 0.6, decay: float = 5.0) -> np.ndarray:
    """A soft note: the fundamental and a quiet octave above, a 4 ms attack and an exponential decay."""
    t = np.arange(int(RATE * seconds)) / RATE
    wave_ = np.sin(2 * np.pi * freq * t) + 0.25 * np.sin(4 * np.pi * freq * t)
    envelope = np.minimum(1.0, t / 0.004) * np.exp(-decay * t / seconds)
    return loudness * wave_ * envelope / 1.25


def sweep(start: float, end: float, seconds: float, loudness: float = 0.6) -> np.ndarray:
    """A tone that glides from `start` to `end` Hz, fading in and out."""
    t = np.arange(int(RATE * seconds)) / RATE
    phase = 2 * np.pi * (start * t + (end - start) * t * t / (2 * seconds))
    envelope = np.minimum(1.0, t / 0.01) * np.minimum(1.0, (seconds - t) / 0.03)
    return loudness * np.sin(phase) * envelope


def crackle(seconds: float, loudness: float = 0.35) -> np.ndarray:
    """A burst of radio static, fading out."""
    noise = np.random.default_rng(7).uniform(-1.0, 1.0, int(RATE * seconds))
    return loudness * noise * np.linspace(1.0, 0.0, len(noise))


def clank(freq: float, seconds: float, loudness: float = 0.7) -> np.ndarray:
    """Metal struck hard by metal: a crack of bright noise, a dull thunk at about `freq`, and a few inharmonic partials
    that die in a few hundredths of a second. Nothing rings: a ring that lasts, or high pitched partials, sound like a
    bell."""
    t = np.arange(int(RATE * seconds)) / RATE
    noise = np.random.default_rng(int(freq)).uniform(-1.0, 1.0, len(t))
    crack = (np.convolve(noise, np.ones(3) / 3, mode='same') - np.convolve(noise, np.ones(14) / 14,
                                                                           mode='same')) * np.exp(-t * 110.0)
    thunk = np.sin(2 * np.pi * freq * t) * np.exp(-t * 38.0)
    clang = sum(strength * np.sin(2 * np.pi * freq * ratio * t + phase) * np.exp(-t * 70.0)
                for ratio, strength, phase in ((1.53, 0.5, 0.7), (2.31, 0.35, 2.1), (3.07, 0.25, 4.0)))
    return loudness * np.clip(1.2 * crack + 0.9 * thunk + clang, -1.0, 1.0) * np.minimum(1.0, t / 0.0008)


def rumble(seconds: float, loudness: float = 0.4) -> np.ndarray:
    """A heavy door sliding: low-pass noise that swells and fades."""
    noise = np.random.default_rng(11).uniform(-1.0, 1.0, int(RATE * seconds))
    low = np.convolve(noise, np.ones(60) / 60, mode='same')
    return loudness * low / np.abs(low).max() * np.sin(np.linspace(0.0, np.pi, len(low)))


def scrape(seconds: float, loudness: float = 0.35) -> np.ndarray:
    """Metal dragged over metal: rough noise, brighter than the rumble, that swells and dies."""
    noise = np.random.default_rng(int(seconds * 1000)).uniform(-1.0, 1.0, int(RATE * seconds))
    rough = noise - np.convolve(noise, np.ones(40) / 40, mode='same')  # no lows: the rumble has those
    return loudness * rough / np.abs(rough).max() * np.sin(np.linspace(0.0, np.pi, len(rough))) ** 0.7


def metal_doors() -> List[np.ndarray]:
    """Ore loaded into the hold, about two seconds of heavy industry: the hatch rumbles and scrapes, a door slams, and
    the load falls in as metal hitting metal, in clusters of uneven gaps and wandering pitch."""
    return [
        rumble(0.3), scrape(0.15), clank(190, 0.15, 0.8), silence(0.1), clank(255, 0.15, 0.7), silence(0.2),
        clank(235, 0.12, 0.65), silence(0.04), clank(180, 0.15, 0.75), silence(0.1), clank(130, 0.25, 0.9),
    ]


def hiss(seconds: float, loudness: float) -> np.ndarray:
    """Hydraulic air: noise that swells and dies, with a low whine rising underneath."""
    t = np.arange(int(RATE * seconds)) / RATE
    noise = np.random.default_rng(3).uniform(-1.0, 1.0, len(t))
    noise = np.convolve(noise, np.ones(2) / 2, mode='same')  # dulls only the very highest frequencies
    envelope = np.sin(np.pi * t / seconds) ** 2
    whine = 0.5 * np.sin(2 * np.pi * (180 * t + 120 * t * t / (2 * seconds)))
    return loudness * (noise + whine) * envelope


def impact(seconds: float, loudness: float) -> np.ndarray:
    """A heavy metal impact: a low thud and a ring of inharmonic partials, over a short burst of noise."""
    t = np.arange(int(RATE * seconds)) / RATE
    thud = np.sin(2 * np.pi * (90 + 110 * np.exp(-t * 40)) * t) * np.exp(-t * 9)
    ring = sum(np.sin(2 * np.pi * freq * t) * np.exp(-t * decay) for freq, decay in ((310, 12), (487, 16), (851, 22),
                                                                                     (1290, 30), (1830, 40)))
    burst = np.random.default_rng(5).uniform(-1.0, 1.0, len(t)) * np.exp(-t * 90)
    return loudness * np.clip(0.8 * thud + 0.45 * ring + 0.9 * burst, -1.0, 1.0)


def machinery(loudness: float) -> np.ndarray:
    """One second of dark industrial drone, made to loop without a click: a 50 Hz transformer buzz and its harmonics,
    and a band of grit (random-phase partials, every one a whole number of Hz) that thins out upwards. Slow irregular
    wobbles (whole Hz again) keep it from sounding electronic."""
    rng = np.random.default_rng(11)
    t = np.arange(RATE) / RATE
    buzz = sum(np.sin(2 * np.pi * 50 * n * t + rng.uniform(0, 6.28)) / n ** 0.8 for n in range(1, 9))
    freqs = np.arange(90, 1800, 7)
    grit = sum(np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28)) * (150 / f) ** 1.2 for f in freqs)
    wobble = 1 + 0.25 * np.sin(2 * np.pi * 3 * t + 1) + 0.15 * np.sin(2 * np.pi * 7 * t
                                                                      + 4) + 0.1 * np.sin(2 * np.pi * 11 * t)
    wave_ = (buzz / 2.5 + grit / 6) * wobble
    return loudness * wave_ / np.max(np.abs(wave_))


def hum(partials: List[Tuple[int, float]], tremolo: int, loudness: float) -> np.ndarray:
    """One second of a steady hum, made to loop without a click: every frequency is a whole number of Hz, so the sound
    ends where it began. `partials` are (Hz, strength); `tremolo` is the wobble in Hz."""
    t = np.arange(RATE) / RATE
    wave_ = sum(strength * np.sin(2 * np.pi * freq * t) for freq, strength in partials)
    wave_ = wave_ / sum(strength for _, strength in partials)
    return loudness * wave_ * (0.8 + 0.2 * np.sin(2 * np.pi * tremolo * t))


def atmosphere(seconds: float, peak: float, loudness: float, seed: int) -> np.ndarray:
    """Air torn by a hull at speed: a deep rumble under a hiss of turbulent noise, with a fast flutter, swelling to its
    loudest at `peak` (0 to 1 of the duration) and fading out. The hiss is brighter the louder it gets, as the air
    thickens."""
    n = int(RATE * seconds)
    t = np.arange(n) / RATE
    noise = np.random.default_rng(seed).uniform(-1.0, 1.0, n)
    rumble_ = np.convolve(noise, np.ones(80) / 80, mode='same')
    rumble_ = rumble_ / np.abs(rumble_).max()
    mid = np.convolve(noise, np.ones(6) / 6, mode='same')
    hiss_ = (noise - np.convolve(noise, np.ones(4) / 4, mode='same')) * 0.5  # the highest part of the noise
    position = t / seconds
    rise = np.where(position < peak, (position / peak) ** 1.5, ((1 - position) / (1 - peak)) ** 1.2)
    flutter = 0.8 + 0.2 * np.sin(2 * np.pi * 23 * t) * np.sin(2 * np.pi * 7 * t + 1)
    wave_ = rumble_ * 0.9 + mid * 0.6 + hiss_ * rise
    return loudness * wave_ * rise * flutter / np.abs(wave_ * rise).max()


def silence(seconds: float) -> np.ndarray:
    return np.zeros(int(RATE * seconds))


def save(name: str, parts: List[np.ndarray]) -> None:
    samples = np.concatenate(parts)
    samples = np.clip(samples, -1.0, 1.0)
    os.makedirs(OUT_DIR, exist_ok=True)
    with wave.open(os.path.join(OUT_DIR, name + '.wav'), 'wb') as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(RATE)
        file.writeframes((samples * 32767).astype('<i2').tobytes())
    print(f'{name}.wav: {len(samples) / RATE:.2f} s')


def main() -> None:
    save('ui_open', [tone(520, 0.06, 0.5), tone(780, 0.09, 0.5)])
    save('ui_close', [tone(780, 0.06, 0.5), tone(520, 0.09, 0.5)])
    save('ui_click', [tone(1300, 0.035, 0.5, decay=7.0)])
    save('board_open', [sweep(400, 1200, 0.12, 0.45), silence(0.04), tone(900, 0.08, 0.45)])
    save('mission_taken', [tone(523.25, 0.09, 0.55), tone(659.25, 0.16, 0.55)])
    save('mission_delivered', [tone(523.25, 0.08, 0.55), tone(659.25, 0.08, 0.55), tone(783.99, 0.08, 0.55),
                               tone(1046.5, 0.3, 0.55)])
    save('mission_failed', [sweep(330, 200, 0.32, 0.55), silence(0.05), tone(180, 0.2, 0.6, decay=4.0)])
    save('notify', [tone(1000, 0.14, 0.45, decay=6.0)])
    save('alert', [tone(880, 0.1, 0.6), tone(660, 0.1, 0.6), tone(880, 0.1, 0.6), tone(660, 0.14, 0.6)])
    save('radio_open', [crackle(0.06), tone(1100, 0.07, 0.4), silence(0.02), tone(1400, 0.09, 0.4)])
    save('ore_collected', metal_doors())
    save('mine_placed', [hiss(0.35, 0.4), impact(0.45, 0.9), silence(0.05), impact(0.3, 0.6)])
    save('mine_refused', [tone(190, 0.1, 0.6), silence(0.04), tone(190, 0.16, 0.6)])
    save('bind', [atmosphere(1.6, 0.3, 0.8, 21)])  # the hull hits the thin air: a quick roar that settles
    save('unbind', [atmosphere(1.2, 0.65, 0.7, 22)])  # the air thins out: a roar that builds and falls away
    save('time_up', [sweep(500, 800, 0.08, 0.45)])
    save('time_down', [sweep(800, 500, 0.08, 0.45)])
    save('game_over', [sweep(400, 70, 1.0, 0.6), tone(55, 0.7, 0.6, decay=3.0)])
    save('laser', [machinery(0.6)])
    save('thrust', [hum([(55, 1.0), (82, 0.6), (110, 0.4), (165, 0.15)], tremolo=3, loudness=0.5)])
    save('scan', [hum([(38, 1.0), (57, 0.5), (76, 0.3)], tremolo=5, loudness=0.35)])  # low, soft: a passive beam


if __name__ == '__main__':
    main()
