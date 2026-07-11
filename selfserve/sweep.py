"""Send leftover SOL back to a destination address.

  uv run python selfserve/sweep.py --keypair ~/world-test.json --dest <ADDR> [--reserve 0.002] [--send]

Leaves --reserve SOL behind for the fee. To recover CASH first, run
`swap.py --from CASH --to SOL` before sweeping. Simulates by default.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _wallet import load_keypair, build_v0, run

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from _rpc import rpc

from solders.pubkey import Pubkey
from solders.system_program import transfer, TransferParams


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keypair", required=True)
    ap.add_argument("--dest", required=True)
    ap.add_argument("--reserve", type=float, default=0.002, help="SOL to leave for fees")
    ap.add_argument("--send", action="store_true")
    a = ap.parse_args()

    kp = load_keypair(a.keypair)
    bal = rpc("getBalance", [str(kp.pubkey())])["value"]
    lamports = bal - int(a.reserve * 1e9)
    if lamports <= 0:
        raise SystemExit(f"balance {bal/1e9:.6f} SOL below reserve {a.reserve}")
    print(f"sweeping {lamports/1e9:.6f} SOL -> {a.dest}")
    ix = transfer(TransferParams(from_pubkey=kp.pubkey(),
                                 to_pubkey=Pubkey.from_string(a.dest), lamports=lamports))
    run(build_v0(kp, [ix]), a.send, "sweep SOL")


if __name__ == "__main__":
    main()
