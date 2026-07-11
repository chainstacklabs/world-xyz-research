"""Read a live prediCt Market account and hand back the accounts split/merge need.

Market layout (decoded in docs/reference.md): 320 bytes, offsets
  40 CASH mint | 72 YES mint | 104 NO mint | 136 vault.
No maker/pool field exists — which is why split isn't maker-gated.
"""
import base64
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from _rpc import rpc, signatures, transaction  # noqa: E402
import base58  # noqa: E402
from solders.pubkey import Pubkey  # noqa: E402

PREDICT = "prediCtPZCttYMvm2W3PtxmMxLmT1dtN7riU6Cxh6tM"
TOKEN22 = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
SPLIT_DISC = hashlib.sha256(b"global:split").digest()[:8].hex()


def _pk(buf, off):
    return str(Pubkey.from_bytes(buf[off:off + 32]))


def read_market(market: str) -> dict:
    v = rpc("getAccountInfo", [market, {"encoding": "base64"}])["value"]
    if not v:
        raise SystemExit(f"market {market} not found (closed/resolved?)")
    buf = base64.b64decode(v["data"][0])
    if len(buf) < 168:
        raise SystemExit(f"market {market} unexpected size {len(buf)}")
    return {"market": market, "cash_mint": _pk(buf, 40), "yes_mint": _pk(buf, 72),
            "no_mint": _pk(buf, 104), "vault": _pk(buf, 136)}


def find_open_market(scan: int = 200) -> str:
    """Freshest market with a recent split whose Market account is still live."""
    for s in signatures(PREDICT, limit=scan):
        if s.get("err"):
            continue
        t = transaction(s["signature"])
        if not t:
            continue
        for g in t["meta"].get("innerInstructions", []):
            for ix in g["instructions"]:
                if (ix.get("programId") == PREDICT and isinstance(ix.get("data"), str)
                        and base58.b58decode(ix["data"])[:8].hex() == SPLIT_DISC):
                    market = ix["accounts"][1]
                    if rpc("getAccountInfo", [market, {"encoding": "base64"}])["value"]:
                        return market
    raise SystemExit("no open market found in scan")


if __name__ == "__main__":
    m = sys.argv[1] if len(sys.argv) > 1 else find_open_market()
    info = read_market(m)
    for k, val in info.items():
        print(f"{k:10} {val}")
