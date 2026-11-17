"""Conservative artifact indicators. Not a de-clicker or intelligibility detector."""

import math


def indicators(samples, rate=16000):
    clipped = 0
    run = 0
    maxrun = 0
    events = []
    last = -rate
    for i, value in enumerate(samples):
        if abs(value) >= 32700:
            clipped += 1
            run += 1
            maxrun = max(maxrun, run)
        else:
            run = 0
        # Isolated high-amplitude impulse with locally quiet neighbours, not ordinary sibilance.
        if (
            2 <= i < len(samples) - 2
            and abs(value) > 16000
            and max(
                abs(samples[i - 2]), abs(samples[i - 1]), abs(samples[i + 1]), abs(samples[i + 2])
            )
            < 2500
            and i - last > rate * 0.02
        ):
            events.append(round(i / rate, 4))
            last = i
    return {
        "clipped_samples": clipped,
        "longest_clipped_run": maxrun,
        "possible_impulse_seconds": events[:100],
        "limitation": "Heuristic warnings only; sibilants and codec artifacts require listening. No automatic audio edits.",
    }
