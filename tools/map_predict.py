"""Reverse prediCt's instruction set from live transactions.

No on-chain IDL, but the program logs `Instruction: <name>`. Sample N recent txs,
attribute each logged instruction name to the program that was executing (by tracking
`Program <id> invoke [depth]` / `success|failed` on the log stack), and tally names
seen under prediCt. Also dump the account roster + discriminator of the first prediCt
top-level instruction found, to seed account-schema work.

Usage: uv run --no-project tools/map_predict.py [N]
"""
import base64
import sys
from collections import Counter

from _rpc import signatures, transaction

PREDICT = "prediCtPZCttYMvm2W3PtxmMxLmT1dtN7riU6Cxh6tM"
KNOWN = {
    "DF1ow4tspfHX9JwWJsAb9epbkA8hmpSEAtxXy1V27QBH": "DFlow",
    "JanusXpm3gsW3c9ErNoUgHppL8dGLvZKB7uekkJEYFP": "JanusFI",
    "2DNbzPochEcyCcWMbL4d9S3u9QqQEj5bbe6cSZFvKsbh": "BisonFI",
    PREDICT: "prediCt",
    "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb": "Token2022",
}


def names_by_program(logs):
    """Walk the log stack; map each 'Instruction: X' to the currently-executing program."""
    stack, out = [], Counter()
    for ln in logs:
        if "invoke [" in ln:
            stack.append(ln.split("Program ", 1)[1].split(" invoke")[0])
        elif ln.endswith("success") or "failed" in ln:
            if stack:
                stack.pop()
        elif "Program log: Instruction: " in ln and stack:
            out[(stack[-1], ln.split("Instruction: ", 1)[1].strip())] += 1
    return out


def main():
    import base58
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    sigs = [s["signature"] for s in signatures(PREDICT, limit=n) if not s.get("err")]
    tally = Counter()
    examples = {}  # discriminator hex -> (sig, n_accounts)
    for i, sig in enumerate(sigs):
        t = transaction(sig)
        if not t:
            continue
        tally.update(names_by_program(t["meta"].get("logMessages", [])))
        for grp in t["meta"].get("innerInstructions", []):
            for ix in grp["instructions"]:
                if ix.get("programId") == PREDICT and isinstance(ix.get("data"), str):
                    raw = base58.b58decode(ix["data"])
                    disc = raw[:8].hex()
                    if disc not in examples:
                        examples[disc] = (sig, len(ix.get("accounts", [])), len(raw))
        if i % 10 == 0:
            print(f"  scanned {i+1}/{len(sigs)}", flush=True)

    print("\n=== instruction names seen, by program (count) ===")
    for (prog, name), c in tally.most_common():
        print(f"  {KNOWN.get(prog, prog[:8]):10} {name:28} {c}")

    print("\n=== distinct prediCt instruction discriminators (from inner ixs) ===")
    for disc, (sig, na, dl) in sorted(examples.items(), key=lambda x: -x[1][1]):
        print(f"  {disc}  accounts={na:2} data_len={dl:3}  e.g. {sig[:16]}…")


if __name__ == "__main__":
    main()
