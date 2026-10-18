"""Generate the sound effects in common/resources/sounds (see common/audio.py).

Run from the project root:  python tools/generate_sounds.py

Simple electronic tones, made with numpy and written as 16-bit mono WAV files: the sounds of a cockpit in vacuum, never of
space. They are placeholders: any WAV of the same name in that folder replaces one.
"""

import os
import wave
from typing import List
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
    save('mission_delivered', [tone(523.25, 0.08, 0.55), tone(659.25, 0.08, 0.55), tone(783.99, 0.08, 0.55), tone(1046.5, 0.3, 0.55)])
    save('mission_failed', [sweep(330, 200, 0.32, 0.55), silence(0.05), tone(180, 0.2, 0.6, decay=4.0)])


if __name__ == '__main__':
    main()
