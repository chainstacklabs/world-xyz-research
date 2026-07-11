"""Fetch on-chain Anchor IDL for a program, if it publishes one.

Anchor IDL account = create_with_seed(base, "anchor:idl", program) where
base = find_program_address([], program).0. Account layout: 8-byte discriminator +
32-byte authority + 4-byte u32 LE data_len + zlib-compressed JSON.

Usage: uv run tools/fetch_idl.py <program_id> [out.json]
"""
import base64
import json
import sys
import zlib

from solders.pubkey import Pubkey

from _rpc import account


def idl_address(program: str) -> Pubkey:
    prog = Pubkey.from_string(program)
    base, _ = Pubkey.find_program_address([], prog)
    return Pubkey.create_with_seed(base, "anchor:idl", prog)


def main():
    program = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else None
    addr = idl_address(program)
    print(f"IDL account: {addr}")
    v = account(str(addr), encoding="base64")
    if not v:
        print("  no IDL account (program is not Anchor, or IDL not published)")
        return
    raw = base64.b64decode(v["data"][0])
    authority = str(Pubkey.from_bytes(raw[8:40]))
    data_len = int.from_bytes(raw[40:44], "little")
    idl = json.loads(zlib.decompress(raw[44:44 + data_len]))
    print(f"  authority: {authority}")
    print(f"  name={idl.get('metadata',{}).get('name') or idl.get('name')} "
          f"version={idl.get('metadata',{}).get('version') or idl.get('version')}")
    ins = idl.get("instructions", [])
    print(f"  instructions ({len(ins)}): {', '.join(i['name'] for i in ins)}")
    accts = idl.get("accounts", [])
    print(f"  accounts ({len(accts)}): {', '.join(a['name'] for a in accts)}")
    if out:
        json.dump(idl, open(out, "w"), indent=2)
        print(f"  wrote {out}")


if __name__ == "__main__":
    main()
