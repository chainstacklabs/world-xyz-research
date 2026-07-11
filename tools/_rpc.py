"""Shared Solana JSON-RPC client for the World dossier.

Reads SOL_RPC from env, else from ../.env, else ../../zonda/case/.env.
Chainstack rejects the default Python-urllib User-Agent (403), so we send a
curl-style UA. Stdlib only — read tools run with `uv run --no-project`.
"""
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ENV_PATHS = [_HERE.parent / ".env"]


def sol_rpc() -> str:
    if url := os.environ.get("SOL_RPC"):
        return url
    for p in _ENV_PATHS:
        if p.exists():
            for line in p.read_text().splitlines():
                if line.startswith("SOL_RPC="):
                    return line.split("=", 1)[1].strip().strip("'\"")
    raise SystemExit("SOL_RPC not set (env or .env)")


def rpc(method: str, params: list, tries: int = 5):
    url, body = sol_rpc(), json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    last = None
    for t in range(tries):
        try:
            req = urllib.request.Request(url, data=body, headers={
                "content-type": "application/json", "user-agent": "curl/8.5.0"})
            r = json.loads(urllib.request.urlopen(req, timeout=90).read())
            if "error" in r:
                raise RuntimeError(r["error"])
            return r["result"]
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            last = e
            time.sleep(1.5 * (t + 1))
    raise SystemExit(f"rpc {method} failed after {tries}: {last}")


def account(pubkey: str, encoding: str = "jsonParsed"):
    return rpc("getAccountInfo", [pubkey, {"encoding": encoding, "maxSupportedTransactionVersion": 0}])["value"]


def signatures(pubkey: str, limit: int = 1000, before: str | None = None):
    opts = {"limit": limit}
    if before:
        opts["before"] = before
    return rpc("getSignaturesForAddress", [pubkey, opts])


def transaction(sig: str):
    return rpc("getTransaction", [sig, {"maxSupportedTransactionVersion": 0, "encoding": "jsonParsed"}])
