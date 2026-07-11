# selfserve/ — transacting directly with World (wallet-signing scripts)

**These scripts sign and broadcast real mainnet transactions** with a wallet you control.
That is the difference from [`../tools/`](../tools/), which is read-only RPC reproduction
(no keys, no sends). Use these only with a throwaway test wallet.

## The finding they demonstrate

`split` and `merge` on `prediCt` are **permissionless**. Any wallet can mint a complete
set (`split`: N CASH → N YES + N NO) and redeem it (`merge`: N YES + N NO → N CASH)
directly, with **no market maker and no ~2% spread** — the maker only appears because
Phantom's frontend routes through one, not because the program requires it.

The program enforces only that the caller signs and owns the CASH source account. Nothing
binds the caller to JanusFI/BisonFI: the Market account stores no maker field, and `split`
receives no registry/allowlist account through which such a check could run. Verified end
to end on mainnet — split then merge, value-conserving to the raw unit. See
[`../docs/reference.md`](../docs/reference.md#splitmerge-are-permissionless).

## Key handling

**You** own the keypair. Every script reads a keyfile path you pass (`--keypair`); none
generates, prints, or transmits a secret. Every script **simulates by default** and only
broadcasts with `--send`. Keyfiles are gitignored.

```bash
uv run python selfserve/keygen.py ~/world-test.json    # generate your keyfile locally
```

Fund it: ~0.05 SOL (fees + rent). CASH is acquired in step 1 below.

## Flow

```bash
KP=~/world-test.json

# 0. see what's there
uv run python selfserve/balances.py <PUBKEY>

# 1. SOL -> CASH (Jupiter; drop --send to dry-run first)
uv run python selfserve/swap.py --keypair $KP --from SOL --to CASH --amount 0.05 --send

# 2. split 1 CASH -> 1 YES + 1 NO in your own wallet (auto-picks an open market)
uv run python selfserve/split.py --keypair $KP --amount 1.0 --send
#    note the market pubkey it prints — you need it for merge

# 3. merge back before the market resolves -> recover 1 CASH
uv run python selfserve/merge.py --keypair $KP --amount 1.0 --market <MARKET> --send

# 4. unwind + return funds
uv run python selfserve/swap.py --keypair $KP --from CASH --to SOL --amount <CASH_LEFT> --send
uv run python selfserve/sweep.py --keypair $KP --dest <YOUR_MAIN_WALLET> --send
```

Each `--send` prints its tx signature; effects are checkable over RPC — CASH into the
vault, YES+NO minted in equal amount to your ATAs, merge burning them 1:1.

## Single-leg buy / sell

Not scripted here. Buying/selling one leg (YES *or* NO) needs a counterparty — the World
maker via the DFlow orchestrator. Outcome tokens have no open AMM route (Jupiter returns
"not tradable") and DFlow builds the route off-chain, so it can't be self-routed; it
requires World's quote endpoint, which is API-key gated. A real buy decodes as a single
signer, so it's doable given that endpoint — but it isn't reproduced here.

## Notes

- Markets are short (BTC up/down ≈15-min windows) and get `close_market`'d after
  resolution. `split.py`/`_market.py` pick a market open at build time; if it resolves
  before you send, the tx fails — just rerun.
- After resolution the winning leg redeems 1 CASH, the loser 0. `merge` before resolution
  to get your CASH back at a 1.0 basis. Net cost ≈ fees + rent + swap slippage.
