"""End-to-end test of the deterministic chain: analyse -> report.

No network. Builds a fixture corpus whose answer is known by construction,
runs the real scripts, and checks the rendered HTML says the right things.
"""
import json, os, re, subprocess, sys, tempfile
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def d(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y%m%d")


def build(tmp):
    corpus, transcripts = [], {}
    for i in range(20):
        for tag, days in (("old", 1000), ("new", 60)):
            vid = f"{tag}{i}"
            text = f"[00:00] filler words for {vid} spoken aloud on camera"
            path = os.path.join(tmp, f"{vid}.txt")
            open(path, "w").write(text)
            transcripts[vid] = text
            corpus.append({
                "id": vid, "channel": f"ch_{vid}", "upload_date": d(days),
                "title": f"{tag} video {i}", "view_count": 1000,
                "url": f"https://www.youtube.com/watch?v={vid}",
                "transcript": path,
            })
    json.dump({"corpus": corpus, "dropped": [{"id": "x", "reason": "no_captions"}]},
              open(f"{tmp}/corpus.json", "w"))

    claims, clusters = [], []

    def cluster(cid, label, vids, contradicts=None):
        ids = []
        for v in vids:
            claim_id = f"{v}#{cid}"
            claims.append({"id": claim_id, "video_id": v, "text": label,
                           "quote": f"filler words for {v}", "t": "00:00",
                           "type": "tactic"})
            ids.append(claim_id)
        c = {"id": cid, "label": label, "description": f"desc {cid}",
             "claim_ids": ids}
        if contradicts:
            c["contradicts"] = contradicts
        clusters.append(c)

    cluster("settled-one", "Hook the viewer in the first 3 seconds",
            [f"old{i}" for i in range(6)] + [f"new{i}" for i in range(6)])
    cluster("expired-one", "Upload every single day",
            [f"old{i}" for i in range(9)], contradicts=["current-one"])
    cluster("current-one", "Upload twice a week, not daily",
            [f"new{i}" for i in range(9)], contradicts=["expired-one"])
    cluster("ghost-ref", "Cluster pointing at nothing",
            [f"new{i}" for i in range(3)], contradicts=["does-not-exist"])

    json.dump({"claims": claims}, open(f"{tmp}/claims.json", "w"))
    json.dump({"clusters": clusters}, open(f"{tmp}/clusters.json", "w"))


def main():
    tmp = tempfile.mkdtemp()
    build(tmp)
    fails = []

    def check(name, cond, detail=""):
        print(f"{'PASS' if cond else 'FAIL'}  {name}{'  ' + detail if detail and not cond else ''}")
        if not cond:
            fails.append(name)

    # Quotes must verify against the fixture transcripts.
    v = subprocess.run([sys.executable, f"{ROOT}/scripts/verify_claims.py",
                        "--corpus", f"{tmp}/corpus.json",
                        "--claims", f"{tmp}/claims.json"],
                       capture_output=True, text=True)
    check("verify_claims passes clean input", v.returncode == 0, v.stdout)

    # A fabricated quote must be caught.
    bad = json.load(open(f"{tmp}/claims.json"))
    bad["claims"][0]["quote"] = "words that appear nowhere in any transcript"
    json.dump(bad, open(f"{tmp}/bad.json", "w"))
    v2 = subprocess.run([sys.executable, f"{ROOT}/scripts/verify_claims.py",
                         "--corpus", f"{tmp}/corpus.json",
                         "--claims", f"{tmp}/bad.json"],
                        capture_output=True, text=True)
    check("verify_claims catches an invented quote",
          v2.returncode == 1 and "quote not in transcript" in v2.stdout)

    # The coverage gate: a partial extraction must not sail through.
    partial = json.load(open(f"{tmp}/claims.json"))
    partial["claims"] = [c for c in partial["claims"]
                         if c["video_id"].startswith("old")]
    json.dump(partial, open(f"{tmp}/partial.json", "w"))
    v3 = subprocess.run([sys.executable, f"{ROOT}/scripts/verify_claims.py",
                         "--corpus", f"{tmp}/corpus.json",
                         "--claims", f"{tmp}/partial.json",
                         "--require-coverage"], capture_output=True, text=True)
    check("coverage gate fails a partial extraction", v3.returncode == 2,
          f"rc={v3.returncode}")

    # ...but passes once every uncovered video is declared skipped.
    covered = {c["video_id"] for c in partial["claims"]}
    all_ids = {v["id"] for v in json.load(open(f"{tmp}/corpus.json"))["corpus"]}
    partial["skipped"] = sorted(all_ids - covered)
    json.dump(partial, open(f"{tmp}/partial.json", "w"))
    v4 = subprocess.run([sys.executable, f"{ROOT}/scripts/verify_claims.py",
                         "--corpus", f"{tmp}/corpus.json",
                         "--claims", f"{tmp}/partial.json",
                         "--require-coverage"], capture_output=True, text=True)
    check("coverage gate passes when silence is declared", v4.returncode == 0,
          f"rc={v4.returncode}")

    a = subprocess.run([sys.executable, f"{ROOT}/scripts/analyse.py",
                        "--corpus", f"{tmp}/corpus.json",
                        "--claims", f"{tmp}/claims.json",
                        "--clusters", f"{tmp}/clusters.json",
                        "--out", f"{tmp}/analysis.json"],
                       capture_output=True, text=True)
    check("analyse runs", a.returncode == 0, a.stderr)

    data = json.load(open(f"{tmp}/analysis.json"))
    got = {c["id"]: c["status"] for c in data["clusters"]}
    check("settled detected", got.get("settled-one") == "settled", str(got))
    check("expired detected", got.get("expired-one") == "expired", str(got))
    check("current detected", got.get("current-one") == "current", str(got))

    pairs = data["summary"]["contradiction_pairs"]
    check("contradiction pair recorded",
          ["current-one", "expired-one"] in [sorted(p) for p in pairs], str(pairs))
    ghost = [c for c in data["clusters"] if c["id"] == "ghost-ref"][0]
    check("dangling contradiction reference dropped", ghost["contradicts"] == [],
          str(ghost["contradicts"]))

    main_report(tmp, check)

    print("\nALL PASS" if not fails else f"\n{len(fails)} FAILURE(S): {fails}")
    return 1 if fails else 0


def main_report(tmp, check):
    r = subprocess.run([sys.executable, f"{ROOT}/scripts/report.py",
                        "--analysis", f"{tmp}/analysis.json",
                        "--corpus", f"{tmp}/corpus.json",
                        "--topic", "test topic",
                        "--out", f"{tmp}/report.html"],
                       capture_output=True, text=True)
    check("report renders", r.returncode == 0, r.stderr)
    html = open(f"{tmp}/report.html", encoding="utf-8").read()
    # Source line wrapping splits phrases, so match on normalised whitespace.
    flat = " ".join(html.split())
    check("report is self-contained (no external fetches)",
          not re.search(r'(src|href)="https?://(?!www\.youtube)', html))
    check("report shows Contested section", "Contested" in html)
    check("report shows Expired section", ">Expired<" in html)
    check("expired position named", "Upload every single day" in html)
    check("evidence deep-links to timestamp", "youtube.com/watch?v=old0&t=0s" in html)
    check("dropped videos disclosed", "1 video could not be fetched" in flat)
    check("singular channel count reads correctly", "1 channels" not in flat)


if __name__ == "__main__":
    sys.exit(main())
