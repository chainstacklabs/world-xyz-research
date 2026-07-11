"""Extract a prediCt handler's exact arithmetic from a live transaction.

prediCt has no IDL, so we read the math from what the handler *does*: the Token-2022
MintTo / Burn / TransferChecked operations it performs (raw amounts). Only prediCt holds
the outcome mints' authority, so any MintTo/Burn of an outcome mint is prediCt's own effect.

Usage: uv run python tools/decode_handler.py <InstructionName> [scan]
  e.g. Split | Merge | RedeemOutcomeForUser | BurnWorthlessOutcome
"""
import hashlib
import sys

import base58

from _rpc import signatures, transaction

PREDICT = "prediCtPZCttYMvm2W3PtxmMxLmT1dtN7riU6Cxh6tM"
CASH = "CASHx9KJUStyftLFWGvEVf59SGeG9sh5FfcnZMVPCASH"
SNAKE = {"Split": "split", "Merge": "merge", "RedeemOutcomeForUser": "redeem_outcome_for_user",
         "BurnWorthlessOutcome": "burn_worthless_outcome", "InitializeMarket": "initialize_market",
         "DetermineOutcome": "determine_outcome", "CloseMarket": "close_market"}


def disc(name):
    return hashlib.sha256(f"global:{SNAKE.get(name, name.lower())}".encode()).digest()[:8].hex()


def has_ix(t, want):
    allix = list(t["transaction"]["message"]["instructions"])
    for g in t["meta"].get("innerInstructions", []):
        allix += g["instructions"]
    return any(ix.get("programId") == PREDICT and isinstance(ix.get("data"), str)
               and base58.b58decode(ix["data"])[:8].hex() == want for ix in allix)


def token_ops(t):
    """All parsed Token-2022 ops in the tx (top + inner), with raw amounts."""
    ops = []
    groups = [t["transaction"]["message"]["instructions"]]
    groups += [g["instructions"] for g in t["meta"].get("innerInstructions", [])]
    for grp in groups:
        for ix in grp:
            p = ix.get("parsed")
            if not isinstance(p, dict):
                continue
            typ = p.get("type", "")
            info = p.get("info", {})
            if typ in ("mintTo", "mintToChecked", "burn", "burnChecked", "transferChecked", "transfer"):
                amt = (info.get("tokenAmount", {}) or {}).get("amount") or info.get("amount")
                mint = info.get("mint", "?")
                ops.append((typ, mint, amt, info.get("authority", info.get("mintAuthority", "")) ))
    return ops


def main():
    name = sys.argv[1]
    scan = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    want = disc(name)
    for s in signatures(PREDICT, limit=scan):
        if s.get("err"):
            continue
        t = transaction(s["signature"])
        if not t or not has_ix(t, want):
            continue
        print(f"{name} (disc {want}) — tx {s['signature'][:24]}…")
        for typ, mint, amt, auth in token_ops(t):
            tag = "CASH" if mint == CASH else ("OUT:" + mint[:6] if mint != "?" else "?")
            print(f"  {typ:16} {tag:12} amount={amt}")
        return
    print(f"no {name} tx found in {scan} sigs")


if __name__ == "__main__":
    main()
