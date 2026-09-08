"""Turn a YouTube auto-caption VTT into clean, timestamped text.

Auto-captions are written in a rolling style: each cue repeats the previous
line plus a few new words, and every word carries an inline <c> timing tag.
Left alone that is roughly 4-6x more text than was actually spoken, which is
paid for twice over in extraction tokens. This collapses it back down.
"""
import re
import sys

CUE = re.compile(r"^(\d\d):(\d\d):(\d\d)\.\d\d\d\s+-->")
TAG = re.compile(r"<[^>]+>")
SKIP_PREFIX = ("Kind:", "Language:", "NOTE", "STYLE", "REGION")


def parse(path):
    """Return [(seconds, text)] with rolling duplicates removed."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        raw = fh.read()

    segments = []
    seen_recently = []
    at = 0

    for line in raw.splitlines():
        cue = CUE.match(line)
        if cue:
            h, m, s = (int(x) for x in cue.groups())
            at = h * 3600 + m * 60 + s
            continue

        text = TAG.sub("", line).strip()
        if not text or text == "WEBVTT" or text.startswith(SKIP_PREFIX):
            continue

        # A rolling caption re-states the tail of the previous cue. Comparing
        # against a short window rather than only the last line catches the
        # two-line scroll pattern as well.
        if text in seen_recently:
            continue
        segments.append((at, text))
        seen_recently.append(text)
        if len(seen_recently) > 4:
            seen_recently.pop(0)

    return segments


def to_text(segments, stamp_every=30):
    """Flatten to prose with a timestamp marker every `stamp_every` seconds.

    Extraction needs enough timestamps to cite a claim, but one per line
    triples the token count for no gain.
    """
    out = []
    next_stamp = 0
    for at, text in segments:
        if at >= next_stamp:
            out.append(f"[{at // 60:02d}:{at % 60:02d}]")
            next_stamp = at + stamp_every
        out.append(text)
    return " ".join(out)


def word_count(segments):
    return sum(len(t.split()) for _, t in segments)


if __name__ == "__main__":
    segs = parse(sys.argv[1])
    print(f"segments={len(segs)} words={word_count(segs)}", file=sys.stderr)
    print(to_text(segs))
