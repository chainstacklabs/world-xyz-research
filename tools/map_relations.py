"""Build the on-chain program relation graph around World.

Samples txs from each anchor (prediCt, JanusFI, BisonFI, CASH mint, DFlow) and parses the
log stack (`Program X invoke [depth]`) to record CPI edges parent→child. Surfaces the full
set of programs in play (completeness check) and who calls whom (relations).

Usage: uv run python tools/map_relations.py [N_per_anchor]
"""
import sys
from collections import Counter, defaultdict

from _rpc import signatures, transaction

LABEL = {
    "prediCtPZCttYMvm2W3PtxmMxLmT1dtN7riU6Cxh6tM": "prediCt",
    "DF1ow4tspfHX9JwWJsAb9epbkA8hmpSEAtxXy1V27QBH": "DFlow",
    "JanusXpm3gsW3c9ErNoUgHppL8dGLvZKB7uekkJEYFP": "JanusFI",
    "2DNbzPochEcyCcWMbL4d9S3u9QqQEj5bbe6cSZFvKsbh": "BisonFI",
    "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb": "Token2022",
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA": "TokenLegacy",
    "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL": "AToken",
    "11111111111111111111111111111111": "System",
    "ComputeBudget111111111111111111111111111111": "ComputeBudget",
    "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK": "Raydium-CLMM",
    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc": "Orca-Whirlpool",
    "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo": "Meteora-DLMM",
    "Gt9S41PtjR58CbG9JhJ3J6vxesqrNAswbWYbLNTMZA3c": "Chainlink-Verifier",
}
ANCHORS = {
    "prediCt": "prediCtPZCttYMvm2W3PtxmMxLmT1dtN7riU6Cxh6tM",
    "JanusFI": "JanusXpm3gsW3c9ErNoUgHppL8dGLvZKB7uekkJEYFP",
    "BisonFI": "2DNbzPochEcyCcWMbL4d9S3u9QqQEj5bbe6cSZFvKsbh",
    "CASH": "CASHx9KJUStyftLFWGvEVf59SGeG9sh5FfcnZMVPCASH",
    "DFlow": "DF1ow4tspfHX9JwWJsAb9epbkA8hmpSEAtxXy1V27QBH",
}


def lab(p):
    return LABEL.get(p, p[:6] + "…")


def edges_from_logs(logs, edge, seen):
    stack = []
    for ln in logs:
        if " invoke [" in ln:
            prog = ln.split("Program ", 1)[1].split(" invoke")[0]
            seen[prog] += 1
            if stack:
                edge[(stack[-1], prog)] += 1
            stack.append(prog)
        elif ln.endswith(" success") or " failed" in ln:
            if stack:
                stack.pop()


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    edge, seen = Counter(), Counter()
    for name, addr in ANCHORS.items():
        got = 0
        for s in signatures(addr, limit=n * 3):
            if s.get("err"):
                continue
            t = transaction(s["signature"])
            if not t:
                continue
            edges_from_logs(t["meta"].get("logMessages", []), edge, seen)
            got += 1
            if got >= n:
                break
        print(f"  sampled {got} txs around {name}", flush=True)

    print("\n=== all programs seen (invocation count) ===")
    for p, c in seen.most_common():
        print(f"  {c:5}  {lab(p):18} {p}")

    print("\n=== CPI edges parent → child (count) ===")
    for (a, b), c in sorted(edge.items(), key=lambda x: -x[1]):
        print(f"  {c:5}  {lab(a):16} → {lab(b)}")


if __name__ == "__main__":
    main()
