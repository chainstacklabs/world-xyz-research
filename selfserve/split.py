"""Self-serve prediCt SPLIT: lock N CASH -> mint N YES + N NO into your wallet.

  uv run python selfserve/split.py --keypair ~/world-test.json --amount 1.0 [--market M] [--send]

Simulates by default. Creates your YES/NO ATAs (idempotent) in the same tx.
No maker, no ~2% spread — you mint the complete set at a true 1.0 basis.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _wallet import load_keypair, build_v0, run
from _market import read_market, find_open_market
from _predict import create_idempotent, split_ix, TOKEN22
from solders.pubkey import Pubkey


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keypair", required=True)
    ap.add_argument("--amount", type=float, required=True, help="CASH to split")
    ap.add_argument("--market", help="market pubkey (default: auto-find an open one)")
    ap.add_argument("--send", action="store_true")
    a = ap.parse_args()

    kp = load_keypair(a.keypair)
    mkt = read_market(a.market) if a.market else read_market(find_open_market())
    print("market:", mkt)
    user = kp.pubkey()
    ixs = [
        create_idempotent(user, user, Pubkey.from_string(mkt["yes_mint"])),
        create_idempotent(user, user, Pubkey.from_string(mkt["no_mint"])),
        split_ix(user, mkt, a.amount),
    ]
    run(build_v0(kp, ixs), a.send, f"split {a.amount} CASH")


if __name__ == "__main__":
    main()
