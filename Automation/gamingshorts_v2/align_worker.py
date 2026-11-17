"""Run in a dedicated supported Python environment; read saved WAV, never synthesize."""

import json, sys
from pathlib import Path


def main():
    import stable_whisper

    job = json.loads(Path(sys.argv[1]).read_text())
    print("Loading CPU word-alignment model...", flush=True)
    model = stable_whisper.load_model(job["model"], device="cpu")
    lines = []
    for i, line in enumerate(job["lines"], 1):
        print(f"Aligning existing narration {i}/{len(job['lines'])}...", flush=True)
        result = model.align(line["audio"], line["text"], language="en")
        if result is None:
            raise RuntimeError("Alignment failed; no synthetic timings will be substituted")
        data = result.to_dict()
        words = [
            {"word": w["word"].strip(), "start": float(w["start"]), "end": float(w["end"])}
            for seg in data["segments"]
            for w in seg.get("words", [])
        ]
        lines.append({"words": words})
    Path(sys.argv[2]).write_text(json.dumps({"lines": lines}, indent=2))


if __name__ == "__main__":
    main()
