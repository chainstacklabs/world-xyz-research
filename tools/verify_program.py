"""Resolve each World program's loader, ProgramData, deploy slot, upgrade authority.

Uses jsonParsed decoding of the BPF upgradeable loader accounts. Reproduces the
program half of ADDRESSES.md.

Usage: uv run --no-project tools/verify_program.py
"""
from _rpc import account

PROGRAMS = {
    "prediCt (World market program)": "prediCtPZCttYMvm2W3PtxmMxLmT1dtN7riU6Cxh6tM",
    "DFlow orchestrator": "DF1ow4tspfHX9JwWJsAb9epbkA8hmpSEAtxXy1V27QBH",
    "JanusFI (market maker)": "JanusXpm3gsW3c9ErNoUgHppL8dGLvZKB7uekkJEYFP",
    "BisonFI (market maker)": "2DNbzPochEcyCcWMbL4d9S3u9QqQEj5bbe6cSZFvKsbh",
}


def main():
    for label, pid in PROGRAMS.items():
        v = account(pid)
        owner = v["owner"]
        parsed = v["data"].get("parsed") if isinstance(v["data"], dict) else None
        print(f"\n== {label} ==\n  program:   {pid}\n  owner:     {owner}  exec={v['executable']}")
        if parsed and parsed.get("type") == "program":
            pd = parsed["info"]["programData"]
            print(f"  programData: {pd}")
            pv = account(pd)
            pp = pv["data"]["parsed"]["info"]
            print(f"  deploy slot: {pp.get('slot')}")
            print(f"  upgrade authority: {pp.get('authority')}  (None = immutable)")
        else:
            print(f"  (non-upgradeable or unparsed; data={str(v['data'])[:60]})")


if __name__ == "__main__":
    main()
