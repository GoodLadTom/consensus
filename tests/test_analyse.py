"""Classification tests. Each case has an answer we know independently."""
import json, os, subprocess, sys, tempfile
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

def d(days_ago):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y%m%d")

def build(tmp, n_old=30, n_recent=30):
    """30 old (3y) + 30 recent (3mo) videos, each its own channel."""
    corpus = []
    for i in range(n_old):
        corpus.append({"id": f"old{i}", "channel": f"ch_old{i}",
                       "upload_date": d(1100), "title": f"old {i}",
                       "view_count": 1000, "url": ""})
    for i in range(n_recent):
        corpus.append({"id": f"new{i}", "channel": f"ch_new{i}",
                       "upload_date": d(90), "title": f"new {i}",
                       "view_count": 1000, "url": ""})
    json.dump({"corpus": corpus, "dropped": []}, open(f"{tmp}/corpus.json", "w"))
    return corpus

def make(tmp, cases):
    """cases: {cluster_id: [video_ids]}"""
    claims, clusters = [], []
    for cid, vids in cases.items():
        ids = []
        for v in vids:
            claim_id = f"{v}#{cid}"
            claims.append({"id": claim_id, "video_id": v, "text": cid,
                           "quote": "q", "t": "00:10"})
            ids.append(claim_id)
        clusters.append({"id": cid, "label": cid, "description": "", "claim_ids": ids})
    json.dump({"claims": claims}, open(f"{tmp}/claims.json", "w"))
    json.dump({"clusters": clusters}, open(f"{tmp}/clusters.json", "w"))

def run(tmp):
    subprocess.run([sys.executable, f"{ROOT}/scripts/analyse.py",
                    "--corpus", f"{tmp}/corpus.json",
                    "--claims", f"{tmp}/claims.json",
                    "--clusters", f"{tmp}/clusters.json",
                    "--out", f"{tmp}/out.json"],
                   capture_output=True, check=True)
    return {c["id"]: c for c in json.load(open(f"{tmp}/out.json"))["clusters"]}

def main():
    tmp = tempfile.mkdtemp()
    build(tmp)
    make(tmp, {
        # backed heavily in both halves -> settled
        "settled_case":  [f"old{i}" for i in range(8)] + [f"new{i}" for i in range(8)],
        # strong in old, silent in recent, big recent corpus -> expired
        "expired_case":  [f"old{i}" for i in range(10)],
        # strong in recent, silent in old -> current
        "current_case":  [f"new{i}" for i in range(10)],
        # only 2 old backers: absence could easily be chance -> fading, NOT expired
        "weak_old_case": [f"old{i}" for i in range(2)],
        # single channel -> thin, never a consensus
        "single_case":   ["old0"],
    })
    got = run(tmp)

    expect = {
        "settled_case": "settled",
        "expired_case": "expired",
        "current_case": "current",
        "weak_old_case": "fading",
        "single_case": "thin",
    }
    fails = 0
    for cid, want in expect.items():
        have = got[cid]["status"]
        ok = have == want
        fails += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {cid:15s} want={want:8s} got={have:8s} "
              f"p_absent={got[cid]['p_absent']} weight={got[cid]['weighted_support']}")

    # A recent claim must outweigh an equally-backed old one.
    s_new = got["current_case"]["weighted_support"]
    s_old = got["expired_case"]["weighted_support"]
    ok = s_new > s_old
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'}  recency weighting: recent={s_new} > old={s_old}")

    # Same channel twice must not count twice.
    make(tmp, {"dup_case": ["old0", "old0"]})
    got2 = run(tmp)
    ok = got2["dup_case"]["channels"] == 1
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'}  duplicate video counted once: "
          f"channels={got2['dup_case']['channels']}")

    # The bug this guards: if extraction never read the recent videos, their
    # silence is not evidence. Calling that "expired" invents dead advice.
    make(tmp, {"unread_case": [f"old{i}" for i in range(10)]})
    got3 = run(tmp)
    ok = got3["unread_case"]["status"] != "expired"
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'}  unread recent videos do not imply expired: "
          f"status={got3['unread_case']['status']}")

    # But when extraction explicitly reports reading them and finding nothing,
    # the silence is real and expired must still fire.
    payload = json.load(open(f"{tmp}/claims.json"))
    payload["skipped"] = [f"new{i}" for i in range(30)]
    json.dump(payload, open(f"{tmp}/claims.json", "w"))
    got4 = run(tmp)
    ok = got4["unread_case"]["status"] == "expired"
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'}  explicitly-read silence still yields expired: "
          f"status={got4['unread_case']['status']}")

    # One recent voice refutes "nobody says this any more".
    make(tmp, {"counterexample_case":
               [f"old{i}" for i in range(10)] + ["new0"]})
    got5 = run(tmp)
    ok = got5["counterexample_case"]["status"] != "expired"
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'}  one recent backer blocks expired: "
          f"status={got5['counterexample_case']['status']}")

    print("\nALL PASS" if not fails else f"\n{fails} FAILURE(S)")
    return 1 if fails else 0

if __name__ == "__main__":
    sys.exit(main())
