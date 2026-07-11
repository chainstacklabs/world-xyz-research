"""Self-serve prediCt MERGE: burn N YES + N NO -> release N CASH back to you.

  uv run python selfserve/merge.py --keypair ~/world-test.json --amount 1.0 --market M [--send]

The exit mirror of split — no maker on the way out either. Use before the market
resolves to recover your CASH at a 1.0 basis (after resolution one leg -> 0).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _wallet import load_keypair, build_v0, run
from _market import read_market
from _predict import merge_ix


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keypair", required=True)
    ap.add_argument("--amount", type=float, required=True, help="complete sets (CASH) to merge")
    ap.add_argument("--market", required=True)
    ap.add_argument("--send", action="store_true")
    a = ap.parse_args()

    kp = load_keypair(a.keypair)
    mkt = read_market(a.market)
    print("market:", mkt)
    run(build_v0(kp, [merge_ix(kp.pubkey(), mkt, a.amount)]), a.send, f"merge {a.amount} CASH")


if __name__ == "__main__":
    main()
