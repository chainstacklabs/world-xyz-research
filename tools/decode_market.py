"""Decode prediCt's 320-byte Market account and derive PDA seeds.

Captures live Market accounts from recent `split` txs (closed markets read null), locates
known pubkeys (YES/NO mint, CASH vault, per-market authority) at byte offsets, decodes i64
timestamps, and brute-forces PDA seeds against prediCt.

Usage: uv run python tools/decode_market.py
"""
import base64
import hashlib
import struct

import base58
from solders.pubkey import Pubkey

from _rpc import account, rpc, signatures, transaction

PREDICT = Pubkey.from_string("prediCtPZCttYMvm2W3PtxmMxLmT1dtN7riU6Cxh6tM")
CASH = "CASHx9KJUStyftLFWGvEVf59SGeG9sh5FfcnZMVPCASH"
SPLIT = hashlib.sha256(b"global:split").digest()[:8].hex()


def recent_splits(n=40, want=5):
    """Return [(market, yes, no, vault)] from split account rosters (idx 1,3,4,6)."""
    out = []
    for s in signatures(str(PREDICT), limit=n):
        if s.get("err"):
            continue
        t = transaction(s["signature"])
        if not t:
            continue
        allix = list(t["transaction"]["message"]["instructions"])
        for g in t["meta"].get("innerInstructions", []):
            allix += g["instructions"]
        for ix in allix:
            if ix.get("programId") == str(PREDICT) and isinstance(ix.get("data"), str) \
               and base58.b58decode(ix["data"])[:8].hex() == SPLIT:
                a = ix.get("accounts", [])
                if len(a) >= 7:
                    out.append((a[1], a[3], a[4], a[6]))
        if len(out) >= want:
            break
    return out


def pubkeys_in(raw):
    """All 32-byte windows as base58, keyed by offset."""
    return {off: str(Pubkey.from_bytes(raw[off:off + 32])) for off in range(8, len(raw) - 31)}


def main():
    tuples = recent_splits()
    markets = [t[0] for t in tuples]
    vals = rpc("getMultipleAccounts", [markets, {"encoding": "base64"}])["value"]
    live = [(t, v) for t, v in zip(tuples, vals) if v]
    print(f"captured {len(tuples)} split markets; {len(live)} still live\n")
    if not live:
        print("all closed already (markets are short-lived) — retry")
        return

    (market, yes, no, vault), v = live[0]
    raw = base64.b64decode(v["data"][0])
    yes_mint = account(yes)
    authority = yes_mint["data"]["parsed"]["info"]["mintAuthority"] if yes_mint else None
    print(f"Market {market}  size={len(raw)}  disc={raw[:8].hex()}")
    print(f"  yes={yes}\n  no={no}\n  vault={vault}\n  authority(mint auth of YES)={authority}")

    off8 = str(Pubkey.from_bytes(raw[8:40]))
    janus = tuples[0]  # (market,yes,no,vault) — janus pool not here; fetch from split acct0 separately
    known = {yes: "YES_mint", no: "NO_mint", vault: "CASH_vault", CASH: "CASH_mint",
             market: "self/authority"}
    pk = pubkeys_in(raw)
    print(f"\n  offset 8 pubkey (unidentified): {off8}")
    print("  pubkey fields located in Market data:")
    for off in range(8, len(raw) - 31):
        if pk[off] in known:
            print(f"    offset {off:3}: {known[pk[off]]:14} {pk[off]}")

    print("\n  tail region 168..320 (hex, 32B rows):")
    for off in range(168, len(raw), 32):
        print(f"    {off:3}: {raw[off:off+32].hex()}")
    print("\n  u64 values across whole account (nonzero):")
    for off in range(8, len(raw) - 7):
        val = struct.unpack_from("<Q", raw, off)[0]
        if 0 < val < 2**53:
            print(f"    u64@{off:3} = {val}")

    on_curve = Pubkey.from_string(market).is_on_curve()
    print(f"\n  market addr on ed25519 curve? {on_curve}  (False → PDA, has seeds)")

    print("\n=== PDA seed brute-force (expanded) ===")
    m = Pubkey.from_string(market)
    seed_pks = {"off8": Pubkey.from_string(off8), "yes": Pubkey.from_string(yes),
                "no": Pubkey.from_string(no), "cash": Pubkey.from_string(CASH)}
    labels = [b"", b"market", b"authority", b"mint_authority", b"vault", b"outcome",
              b"market_authority", b"prediction", b"event", b"m", b"pool"]
    u64s = {f"u64@{off}": struct.unpack_from("<Q", raw, off)[0] for off in range(8, 312, 4)}
    found = False
    for lab in labels:
        # [label], [label, pk], [label, u64], [pk], [label,pk,u64]
        combos = [[lab]] if lab else []
        for pkn, pkv in seed_pks.items():
            combos.append(([lab, bytes(pkv)], f"{lab.decode()}+{pkn}"))
            for un, uv in u64s.items():
                if uv < 2**40:
                    combos.append(([lab, bytes(pkv), struct.pack("<Q", uv)], f"{lab.decode()}+{pkn}+{un}"))
        for un, uv in u64s.items():
            if uv and uv < 2**40:
                combos.append(([lab, struct.pack("<Q", uv)], f"{lab.decode()}+{un}"))
        for item in combos:
            seeds, desc = item if isinstance(item, tuple) else (item, lab.decode() or "empty")
            try:
                pda, bump = Pubkey.find_program_address(seeds, PREDICT)
            except Exception:
                continue
            if pda == m:
                print(f"  MATCH market PDA: seeds=[{desc}] bump={bump}")
                found = True
    if not found:
        print("  no match — seed uses an ingredient not in {labels, off8/yes/no/cash, account u64s}")


if __name__ == "__main__":
    main()
