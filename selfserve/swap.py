"""Swap via Jupiter (SOL<->CASH or any pair). Used to fund the wallet with CASH
and to unwind CASH back to SOL at the end.

  uv run python selfserve/swap.py --keypair ~/world-test.json --from SOL --to CASH --amount 0.1 [--send]
  uv run python selfserve/swap.py --keypair ~/world-test.json --from CASH --to SOL --amount 5 [--send]

--amount is in the INPUT token's human units. Simulates by default.
Jupiter returns a ready-built versioned tx; we just sign and send it.
"""
import argparse
import base64
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _wallet import load_keypair, simulate, send, confirm
from solders.transaction import VersionedTransaction

JUP = "https://lite-api.jup.ag/swap/v1"
MINTS = {
    "SOL": ("So11111111111111111111111111111111111111112", 9),
    "CASH": ("CASHx9KJUStyftLFWGvEVf59SGeG9sh5FfcnZMVPCASH", 6),
    "USDC": ("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", 6),
}


def _post(url, obj):
    req = urllib.request.Request(url, data=json.dumps(obj).encode(),
                                 headers={"content-type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=60).read())


def _get(url):
    return json.loads(urllib.request.urlopen(urllib.request.Request(url), timeout=60).read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keypair", required=True)
    ap.add_argument("--from", dest="src", required=True, choices=MINTS)
    ap.add_argument("--to", dest="dst", required=True, choices=MINTS)
    ap.add_argument("--amount", type=float, required=True)
    ap.add_argument("--slippage-bps", type=int, default=100)
    ap.add_argument("--send", action="store_true")
    a = ap.parse_args()

    kp = load_keypair(a.keypair)
    in_mint, in_dec = MINTS[a.src]
    out_mint, out_dec = MINTS[a.dst]
    raw_in = int(round(a.amount * 10 ** in_dec))

    q = _get(f"{JUP}/quote?inputMint={in_mint}&outputMint={out_mint}"
             f"&amount={raw_in}&slippageBps={a.slippage_bps}")
    out = int(q["outAmount"]) / 10 ** out_dec
    print(f"quote: {a.amount} {a.src} -> ~{out:.6f} {a.dst} "
          f"(impact {q.get('priceImpactPct')}, {len(q['routePlan'])} hop)")

    swap = _post(f"{JUP}/swap", {
        "quoteResponse": q, "userPublicKey": str(kp.pubkey()),
        "wrapAndUnwrapSol": True, "dynamicComputeUnitLimit": True,
        "prioritizationFeeLamports": {"priorityLevelWithMaxLamports":
                                      {"maxLamports": 2_000_000, "priorityLevel": "medium"}}})
    tx = VersionedTransaction.from_bytes(base64.b64decode(swap["swapTransaction"]))
    signed = VersionedTransaction(tx.message, [kp])

    sim = simulate(signed)
    print("simulate err:", sim.get("err"))
    for l in (sim.get("logs") or [])[-12:]:
        print("   ", l)
    if sim.get("err"):
        raise SystemExit("swap simulation failed — not sending")
    if not a.send:
        print("dry-run OK. re-run with --send to broadcast.")
        return
    sig = send(signed)
    print("sent:", sig)
    st = confirm(sig)
    print("status:", st.get("confirmationStatus") if st else "TIMEOUT")


if __name__ == "__main__":
    main()
