"""Show a wallet's SOL + CASH + per-market YES/NO balances.

  uv run python selfserve/balances.py <PUBKEY> [YES_MINT NO_MINT ...]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from _rpc import rpc

CASH = "CASHx9KJUStyftLFWGvEVf59SGeG9sh5FfcnZMVPCASH"
T22 = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"


def token_bal(owner, mint):
    r = rpc("getTokenAccountsByOwner", [owner, {"mint": mint}, {"encoding": "jsonParsed"}])["value"]
    total = 0.0
    for a in r:
        total += float(a["account"]["data"]["parsed"]["info"]["tokenAmount"]["uiAmount"] or 0)
    return total


def main():
    owner = sys.argv[1]
    lamports = rpc("getBalance", [owner])["value"]
    print(f"SOL   {lamports / 1e9:.6f}")
    print(f"CASH  {token_bal(owner, CASH):.6f}")
    for mint in sys.argv[2:]:
        print(f"tok   {mint[:8]}… {token_bal(owner, mint):.6f}")


if __name__ == "__main__":
    main()
