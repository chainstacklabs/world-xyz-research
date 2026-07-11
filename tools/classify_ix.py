"""Label a prediCt instruction's accounts by classifying each on-chain.

prediCt has no IDL, so account roles aren't named. This finds a live tx for a given
instruction name, then for prediCt's instruction it fetches every account and classifies
it (owner program, parsed type, token mint/owner, executable) so roles can be inferred.

Usage: uv run tools/classify_ix.py <InstructionName>   e.g. Split | InitializeMarket
"""
import hashlib
import sys

import base58

from _rpc import rpc, signatures, transaction

PREDICT = "prediCtPZCttYMvm2W3PtxmMxLmT1dtN7riU6Cxh6tM"
# PascalCase (as logged) -> snake_case for the anchor global discriminator
SNAKE = {"Split": "split", "Merge": "merge", "InitializeMarket": "initialize_market",
         "DetermineOutcome": "determine_outcome", "CloseMarket": "close_market",
         "UpdateMetadata": "update_metadata", "CreateUserSettings": "create_user_settings",
         "UpdateUserSettings": "update_user_settings", "CloseUserSettings": "close_user_settings"}


def disc_of(name):
    snake = SNAKE.get(name, name.lower())
    return hashlib.sha256(f"global:{snake}".encode()).digest()[:8].hex()
OWNERS = {
    "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb": "Token2022",
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA": "TokenLegacy",
    "11111111111111111111111111111111": "System",
    PREDICT: "prediCt-owned",
}


def find_ix(name, scan=200):
    want = disc_of(name)
    for s in signatures(PREDICT, limit=scan):
        if s.get("err"):
            continue
        t = transaction(s["signature"])
        if not t:
            continue
        allix = list(t["transaction"]["message"]["instructions"])
        for grp in t["meta"].get("innerInstructions", []):
            allix += grp["instructions"]
        for ix in allix:
            if ix.get("programId") == PREDICT and isinstance(ix.get("data"), str):
                if base58.b58decode(ix["data"])[:8].hex() == want:
                    return s["signature"], ix, want
    return None, None, want


def classify(pubkeys):
    vals = rpc("getMultipleAccounts", [pubkeys, {"encoding": "jsonParsed"}])["value"]
    out = []
    for pk, v in zip(pubkeys, vals):
        if not v:
            out.append((pk, "MISSING/closed"))
            continue
        owner = OWNERS.get(v["owner"], v["owner"][:10])
        d = v.get("data")
        info = d.get("parsed", {}).get("info", {}) if isinstance(d, dict) else {}
        typ = d.get("parsed", {}).get("type", "") if isinstance(d, dict) else "raw"
        extra = ""
        if typ == "account":
            extra = f"tokenAcct mint={info.get('mint','?')[:8]} owner={info.get('owner','?')[:8]}"
        elif typ == "mint":
            extra = f"MINT dec={info.get('decimals')} supply={info.get('supply')}"
        elif v.get("executable"):
            extra = "PROGRAM"
        else:
            extra = f"space={v.get('space')}"
        out.append((pk, f"{owner:12} {typ:8} {extra}"))
    return out


def main():
    name = sys.argv[1]
    sig, ix, disc = find_ix(name)
    if not ix:
        print(f"no live {name} found")
        return
    accts = ix.get("accounts", [])
    print(f"{name}: tx {sig[:20]}…  discriminator={disc}  accounts={len(accts)}")
    for i, (pk, desc) in enumerate(classify(accts)):
        print(f"  [{i:2}] {pk}  {desc}")


if __name__ == "__main__":
    main()
