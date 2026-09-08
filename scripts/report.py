"""Render the analysed clusters into one self-contained HTML file."""
import argparse
import html
import json
from datetime import datetime

STATUS = {
    "settled":  ("Settled", "Backed across both older and recent videos. This has survived a changing platform."),
    "expired":  ("Expired", "Well backed in older videos and absent from recent ones, by more than chance would explain. Treat as dead advice."),
    "current":  ("Current", "Backed by recent videos and absent from older ones. Something changed."),
    "emerging": ("Emerging", "Leaning recent, but not yet enough backing to separate from chance."),
    "fading":   ("Fading", "Leaning old, but the recent silence is not yet statistically meaningful."),
    "thin":     ("Thin", "Too few independent channels to call. Listed for completeness."),
}
ORDER = ["settled", "expired", "current", "emerging", "fading", "thin"]

CSS = """
*{box-sizing:border-box}
:root{
 --ink:#161513; --muted:#6b6862; --line:#e2ddd4; --ground:#faf8f4; --card:#fff;
 --settled:#2f6f4e; --expired:#a8442a; --current:#2d5c86; --neutral:#8a8580;
 --accent:#3f3a33;
}
body{margin:0;background:var(--ground);color:var(--ink);
 font:16px/1.6 ui-serif,Georgia,"Times New Roman",serif;}
.wrap{max-width:940px;margin:0 auto;padding:56px 24px 96px}
h1{font-size:2.6rem;line-height:1.15;margin:0 0 8px;letter-spacing:-.02em}
.topic{font-style:italic;color:var(--accent)}
.sub{color:var(--muted);font:14px/1.5 ui-sans-serif,system-ui,sans-serif;margin:0 0 32px}
.stats{display:flex;flex-wrap:wrap;gap:28px;padding:20px 24px;background:var(--card);
 border:1px solid var(--line);border-radius:10px;margin-bottom:14px}
.stat b{display:block;font:600 1.5rem/1.2 ui-sans-serif,system-ui,sans-serif}
.stat span{font:12px/1.4 ui-sans-serif,system-ui,sans-serif;color:var(--muted);
 text-transform:uppercase;letter-spacing:.07em}
.method{font:13px/1.6 ui-sans-serif,system-ui,sans-serif;color:var(--muted);
 background:var(--card);border:1px solid var(--line);border-radius:10px;
 padding:16px 20px;margin-bottom:44px}
.method summary{cursor:pointer;font-weight:600;color:var(--accent)}
.method p{margin:12px 0 0}
section{margin-bottom:52px}
.shead{display:flex;align-items:baseline;gap:12px;border-bottom:2px solid var(--ink);
 padding-bottom:8px;margin-bottom:6px}
.shead h2{font-size:1.5rem;margin:0;letter-spacing:-.01em}
.count{font:12px/1 ui-sans-serif,system-ui,sans-serif;color:var(--muted);
 letter-spacing:.06em;text-transform:uppercase}
.sdesc{font:13px/1.6 ui-sans-serif,system-ui,sans-serif;color:var(--muted);margin:0 0 22px}
.claim{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--neutral);
 border-radius:8px;margin-bottom:12px;overflow:hidden}
.claim[data-s="settled"]{border-left-color:var(--settled)}
.claim[data-s="expired"]{border-left-color:var(--expired)}
.claim[data-s="current"]{border-left-color:var(--current)}
.claim>summary{cursor:pointer;padding:16px 20px;list-style:none;display:block}
.claim>summary::-webkit-details-marker{display:none}
.claim>summary:hover{background:#fdfcfa}
.label{font-weight:600;font-size:1.08rem;display:block;margin-bottom:6px}
.desc{font:13px/1.5 ui-sans-serif,system-ui,sans-serif;color:var(--muted);
 margin:0 0 10px;max-width:66ch}
.meta{display:flex;flex-wrap:wrap;gap:14px;align-items:center;
 font:12px/1 ui-sans-serif,system-ui,sans-serif;color:var(--muted)}
.pill{background:#f1ede6;border-radius:20px;padding:4px 10px;white-space:nowrap}
.bar{display:inline-flex;height:7px;width:130px;border-radius:4px;overflow:hidden;
 background:#eae5dc;vertical-align:middle}
.bar i{display:block;height:100%}
.bar .r{background:var(--current)} .bar .o{background:var(--neutral)}
.ev{padding:4px 20px 18px;border-top:1px solid var(--line);background:#fdfcfa}
.q{margin:14px 0 0;padding-left:14px;border-left:2px solid var(--line)}
.q p{margin:0 0 4px;font-size:.95rem}
.q cite{font:12px/1.5 ui-sans-serif,system-ui,sans-serif;color:var(--muted);font-style:normal}
.q a{color:var(--current);text-decoration:none}
.q a:hover{text-decoration:underline}
.vs{display:grid;grid-template-columns:1fr auto 1fr;gap:16px;align-items:center;
 background:var(--card);border:1px solid var(--line);border-radius:8px;
 padding:16px 20px;margin-bottom:12px}
.vs .side b{display:block;font-size:1rem;margin-bottom:8px}
.vsmid{font:11px/1 ui-sans-serif,system-ui,sans-serif;color:var(--muted);
 text-transform:uppercase;letter-spacing:.1em;white-space:nowrap}
@media(max-width:600px){.vs{grid-template-columns:1fr}.vsmid{text-align:center}}
.empty{font:13px/1.6 ui-sans-serif,system-ui,sans-serif;color:var(--muted);font-style:italic}
footer{border-top:1px solid var(--line);padding-top:20px;color:var(--muted);
 font:12px/1.7 ui-sans-serif,system-ui,sans-serif}
@media(max-width:600px){.wrap{padding:32px 16px 64px}h1{font-size:1.9rem}}
"""


def esc(s):
    return html.escape(str(s if s is not None else ""))


def ts_link(video_id, t):
    """Deep-link to the moment a claim was made."""
    secs = 0
    if t:
        parts = str(t).strip("[]").split(":")
        try:
            parts = [int(p) for p in parts]
            secs = parts[0] * 60 + parts[1] if len(parts) == 2 else parts[0]
        except (ValueError, IndexError):
            secs = 0
    return f"https://www.youtube.com/watch?v={video_id}&t={secs}s"


def plural(n, word):
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def bar(recent, old):
    total = recent + old
    if not total:
        return ""
    r = round(100 * recent / total)
    return (f'<span class="bar" title="{recent} recent, {old} older">'
            f'<i class="r" style="width:{r}%"></i>'
            f'<i class="o" style="width:{100 - r}%"></i></span>')


def render_cluster(c, corpus):
    ev = []
    for e in sorted(c["evidence"],
                    key=lambda x: x.get("upload_date") or "", reverse=True):
        v = corpus.get(e["video_id"], {})
        date = e.get("upload_date") or ""
        pretty = f"{date[:4]}-{date[4:6]}" if len(date) == 8 else "undated"
        quote = e.get("quote") or e.get("text") or ""
        ev.append(
            f'<div class="q"><p>&ldquo;{esc(quote)}&rdquo;</p>'
            f'<cite>{esc(v.get("channel") or "unknown")} &middot; {pretty} &middot; '
            f'<a href="{ts_link(e["video_id"], e.get("t"))}" target="_blank" '
            f'rel="noopener">{esc(v.get("title") or e["video_id"])[:70]}'
            f'{" &rarr;" if v.get("title") else ""}</a></cite></div>')

    span = ""
    if c.get("oldest_years") is not None:
        span = f'<span class="pill">spans {c["oldest_years"]:.1f}y</span>'
    contra = ""
    if c.get("contradicts"):
        n = len(c["contradicts"])
        contra = (f'<span class="pill">contested by {n} '
                  f'{"position" if n == 1 else "positions"}</span>')
    p = ""
    if c.get("p_absent") is not None and c["status"] in ("expired", "current"):
        p = f'<span class="pill">absence p={c["p_absent"]:.3f}</span>'

    return (
        f'<details class="claim" data-s="{c["status"]}"><summary>'
        f'<span class="label">{esc(c.get("label") or c["id"])}</span>'
        f'<p class="desc">{esc(c.get("description"))}</p>'
        f'<span class="meta">'
        f'{bar(c["channels_recent"], c["channels_old"])}'
        f'<span class="pill"><b>{c["channels"]}</b> '
        f'{"channel" if c["channels"] == 1 else "channels"}</span>'
        f'<span class="pill">{c["channels_recent"]} recent / {c["channels_old"]} older</span>'
        f'{span}{p}{contra}'
        f'<span class="pill">weight {c["weighted_support"]}</span>'
        f'</span></summary>'
        f'<div class="ev">{"".join(ev)}</div></details>')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--analysis", required=True)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--topic", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    data = json.load(open(a.analysis))
    s, clusters = data["summary"], data["clusters"]
    corpus = {v["id"]: v for v in json.load(open(a.corpus))["corpus"]}
    dropped = json.load(open(a.corpus)).get("dropped", [])

    body = []
    by_id = {c["id"]: c for c in clusters}
    pairs = s.get("contradiction_pairs") or []
    if pairs:
        rows = []
        for a_id, b_id in pairs:
            x, y = by_id.get(a_id), by_id.get(b_id)
            if not x or not y:
                continue
            rows.append(
                f'<div class="vs"><div class="side"><b>{esc(x.get("label") or x["id"])}</b>'
                f'<span class="meta"><span class="pill">{plural(x["channels"], "channel")}</span>'
                f'<span class="pill">{x["status"]}</span></span></div>'
                f'<div class="vsmid">against</div>'
                f'<div class="side"><b>{esc(y.get("label") or y["id"])}</b>'
                f'<span class="meta"><span class="pill">{plural(y["channels"], "channel")}</span>'
                f'<span class="pill">{y["status"]}</span></span></div></div>')
        if rows:
            body.append(
                '<section><div class="shead"><h2>Contested</h2>'
                f'<span class="count">{len(rows)} '
                f'{"disagreement" if len(rows) == 1 else "disagreements"}</span></div>'
                '<p class="sdesc">Positions that directly contradict each other. '
                'Reported as a disagreement rather than averaged into a middle '
                'that nobody actually holds.</p>' + "".join(rows) + '</section>')

    for status in ORDER:
        group = [c for c in clusters if c["status"] == status]
        if not group:
            continue
        title, blurb = STATUS[status]
        body.append(
            f'<section><div class="shead"><h2>{title}</h2>'
            f'<span class="count">{len(group)} '
            f'{"position" if len(group) == 1 else "positions"}</span></div>'
            f'<p class="sdesc">{blurb}</p>'
            + "".join(render_cluster(c, corpus) for c in group) + "</section>")

    if not clusters:
        body.append('<p class="empty">No clusters survived analysis.</p>')

    gen = datetime.fromisoformat(s["generated"]).strftime("%d %B %Y")
    unread = s.get("corpus_unread") or 0
    unread_note = ""
    if unread:
        unread_note = (f" A further {plural(unread, 'video')} were fetched but "
                       f"not read, so they are excluded from the maths entirely "
                       f"rather than counted as silence.")
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Consensus: {esc(a.topic)}</title><style>{CSS}</style></head><body>
<div class="wrap">
<h1>What YouTube agrees on about<br><span class="topic">{esc(a.topic)}</span></h1>
<p class="sub">Generated {gen} &middot; consensus</p>
<div class="stats">
 <div class="stat"><b>{s["corpus_total"]}</b><span>videos read</span></div>
 <div class="stat"><b>{s["corpus_recent"]}</b><span>last {int(s["recent_months"])} months</span></div>
 <div class="stat"><b>{s["corpus_old"]}</b><span>older</span></div>
 <div class="stat"><b>{len(clusters)}</b><span>positions found</span></div>
 <div class="stat"><b>{s["status_counts"].get("expired", 0)}</b><span>expired</span></div>
</div>
<details class="method"><summary>How to read this, and what it cannot tell you</summary>
<p>Every claim is tied to the video that made it and weighted by that video's
age, halving every {s["half_life_years"]} years. Support is counted in distinct
<em>channels</em>, not videos, so one person uploading the same advice five
times counts once.</p>
<p><strong>Expired</strong> is the one that needs care. It means a position was
well backed in older videos and is absent from recent ones by more than chance
would explain, tested against how often we would expect to see it if it were
still current, at a threshold of p&nbsp;&lt;&nbsp;{s["alpha"]}. Where the
absence could plausibly be chance, the position is filed under
<em>fading</em> instead and no claim is made.</p>
<p>This measures what creators <em>say</em>, not what is true. Popular advice
and correct advice are different things, and a consensus of people copying
each other is still only one idea. {plural(len(dropped), "video")} could not be
fetched or had no usable captions.{unread_note} Quotes come from automatic
captions, which mangle names and jargon.</p></details>
{"".join(body)}
<footer>consensus &middot; transcripts via yt-dlp &middot; no video downloaded &middot;
every position traceable to a timestamped source</footer>
</div></body></html>"""

    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(doc)
    print(f"wrote {a.out} ({len(doc) // 1024}KB, {len(clusters)} clusters)")


if __name__ == "__main__":
    main()
