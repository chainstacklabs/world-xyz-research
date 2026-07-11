"""Generate a fresh test keypair YOU control. Run it yourself; the secret is
written only to your local file and printed nowhere. Output format matches
solana-keygen (a 64-int JSON array), so the other selfserve/ scripts read it directly.

  uv run python selfserve/keygen.py ~/world-test.json
"""
import json
import os
import sys
from pathlib import Path

from solders.keypair import Keypair


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: uv run python selfserve/keygen.py <OUTPUT_PATH.json>")
    out = Path(sys.argv[1]).expanduser()
    if out.exists():
        raise SystemExit(f"refusing to overwrite existing {out}")
    kp = Keypair()
    out.write_text(json.dumps(list(bytes(kp))))
    os.chmod(out, 0o600)
    print(f"keyfile: {out}  (chmod 600 — keep it secret, it's gitignored)")
    print(f"pubkey : {kp.pubkey()}")


if __name__ == "__main__":
    main()
