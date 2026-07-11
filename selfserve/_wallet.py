"""Shared signing/sending helpers for the live World test scripts.

The keypair is YOURS: these helpers only ever *read* a keyfile path you pass on
the command line (solana-keygen JSON = a 64-int array). Nothing here generates,
prints, or transmits a secret. Every script simulates first and broadcasts only
when you pass --send.
"""
import base64
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from _rpc import rpc  # noqa: E402

from solders.keypair import Keypair  # noqa: E402
from solders.transaction import VersionedTransaction  # noqa: E402
from solders.message import MessageV0  # noqa: E402
from solders.hash import Hash  # noqa: E402


def load_keypair(path: str) -> Keypair:
    raw = json.loads(Path(path).expanduser().read_text())
    return Keypair.from_bytes(bytes(raw))


def blockhash() -> Hash:
    r = rpc("getLatestBlockhash", [{"commitment": "finalized"}])
    return Hash.from_string(r["value"]["blockhash"])


def build_v0(payer: Keypair, ixs, signers=None) -> VersionedTransaction:
    msg = MessageV0.try_compile(payer.pubkey(), ixs, [], blockhash())
    return VersionedTransaction(msg, [payer, *(signers or [])])


def simulate(tx: VersionedTransaction) -> dict:
    raw = base64.b64encode(bytes(tx)).decode()
    return rpc("simulateTransaction", [raw, {
        "sigVerify": False, "replaceRecentBlockhash": True,
        "encoding": "base64", "commitment": "processed"}])["value"]


def send(tx: VersionedTransaction) -> str:
    raw = base64.b64encode(bytes(tx)).decode()
    return rpc("sendTransaction", [raw, {"encoding": "base64", "skipPreflight": False,
                                         "maxRetries": 5, "preflightCommitment": "processed"}])


def confirm(sig: str, tries: int = 40) -> dict | None:
    for _ in range(tries):
        r = rpc("getSignatureStatuses", [[sig], {"searchTransactionHistory": True}])["value"][0]
        if r and r.get("confirmationStatus") in ("confirmed", "finalized"):
            return r
        time.sleep(2)
    return None


def run(tx: VersionedTransaction, do_send: bool, label: str):
    """Simulate, print logs; broadcast + confirm only if do_send."""
    sim = simulate(tx)
    print(f"[{label}] simulate err: {sim.get('err')}")
    for l in sim.get("logs") or []:
        print("   ", l)
    if sim.get("err"):
        raise SystemExit(f"[{label}] simulation failed — not sending")
    if not do_send:
        print(f"[{label}] dry-run OK. re-run with --send to broadcast.")
        return None
    sig = send(tx)
    print(f"[{label}] sent: {sig}")
    st = confirm(sig)
    print(f"[{label}] status: {st.get('confirmationStatus') if st else 'TIMEOUT'} err={st.get('err') if st else '?'}")
    return sig
