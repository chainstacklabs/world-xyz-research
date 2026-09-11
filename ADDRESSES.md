# Addresses

Every on-chain address the research relies on, with its role and how it was verified.
Mainnet-beta. Addresses verified 2026-07-10; program state re-checked 2026-09-11.
Reproduce with the tools in [`tools/`](tools/); the
narrative for each lives in [`docs/reference.md`](docs/reference.md) and
[`docs/trust-model.md`](docs/trust-model.md).

## Programs

| Program | Address | Role | Upgrade authority | Deploy slot | Verified how |
|---|---|---|---|---|---|
| **prediCt** | `prediCtPZCttYMvm2W3PtxmMxLmT1dtN7riU6Cxh6tM` | World market program — `split`/`merge` complete sets, `determine_outcome`, `redeem_outcome_for_user`, `close_market`. Anchor, IDL withheld. | `6YrRV52Eq3qmWYyMsq9Wn3kCTokk1xYQJgpKQTWrKj7b` (World) | 429,950,041 | `tools/verify_program.py` → ProgramData → upgrade authority |
| **JanusFI** | `JanusXpm3gsW3c9ErNoUgHppL8dGLvZKB7uekkJEYFP` | Market-maker AMM, CPIs `prediCt.split/merge`. Shares prediCt's upgrade key → **World's own MM**. | `6YrRV52Eq3qmWYyMsq9Wn3kCTokk1xYQJgpKQTWrKj7b` (same as prediCt) | 431,476,444 | `verify_program.py`; CPI edges via `tools/map_relations.py` |
| **BisonFI** | `2DNbzPochEcyCcWMbL4d9S3u9QqQEj5bbe6cSZFvKsbh` | Market-maker AMM, CPIs `prediCt.split/merge`. **Independent** — own key. | `6dDjBZdpafRKe7WuVHYTF1HphW1BWiKqioMD5eBGYipS` | 431,241,143 | `verify_program.py`; CPI edges via `map_relations.py` |
| **BiSoNH** | `BiSoNHVpsVZW2F7rx2eQ59yQwKxzU5NvBcmKshCSUypi` | Second Bison program (legacy SPL Token, never CPIs prediCt). Spot-swap venue on the pay-in ramp — executes SOL→USDC→CASH legs inside DFlow routes ([`docs/reference.md`](docs/reference.md#peripheral-liquidity-not-world--the-cashusdcsol-onoff-ramp)). | `6dDjBZdpafRKe7WuVHYTF1HphW1BWiKqioMD5eBGYipS` (same as BisonFI) | — | `verify_program.py`; leg decode via `getTransaction` |
| **DFlow orchestrator** | `DF1ow4tspfHX9JwWJsAb9epbkA8hmpSEAtxXy1V27QBH` | RFQ router / entrypoint (`swap`, `swap_with_destination`). Third-party. IDL published. | `9uo2iJKJkmiYwy5MrkrbGQXbPqwHXqvQaUqxhCkowgsh` | 431,673,740 | `tools/fetch_idl.py DF1ow…` pulls the on-chain IDL |

All four are upgradeable (BPFLoaderUpgradeable) — none immutable. prediCt was deployed
first; all loaders/slots via `getAccountInfo` → ProgramData.

> **Re-checked 2026-09-11 — two programs have been upgraded since this table was written.**
> The slot column is the *last ProgramData write*, not the original deployment, so it moves
> on every upgrade:
>
> | Program | slot above | slot on 2026-09-11 |
> |---|---|---|
> | prediCt | 429,950,041 | **436,239,452** |
> | DFlow orchestrator | 431,673,740 | **445,366,103** |
>
> Upgrade authorities are unchanged. The prediCt upgrade is where two instructions absent
> from the original survey came from — see
> [the instruction set](docs/reference.md#predict-instruction-set). Anything in this repo
> describing prediCt's behaviour should be read against the version it was surveyed on.

## $CASH — collateral (Bridge-issued stablecoin, not a World asset)

| Field | Address / value | Verified how |
|---|---|---|
| Mint | `CASHx9KJUStyftLFWGvEVf59SGeG9sh5FfcnZMVPCASH` | `getAccountInfo` — Token-2022, 6 decimals |
| Supply | ~125M CASH, actively minted (moving) | `getTokenSupply` |
| Mint authority | `HJT2TXrhbWta2ax7V86vcnmX7ZmAVzua4v2yrGwchXB7` | mint account fields |
| Permanent delegate + close authority | `E7JdFMP5AqdndJKstZV2mHdekLwAQbNWRHMpoozyB3qw` | Token-2022 extension — **can claw back / burn any holder** |
| Freeze authority | `AyCP3oW19DHZKvx8oU6mvseW2qn7XfmQ5STrXPa6prY5` | mint account fields |
| Metadata update + transferHook authority | `3etmwgxP4Lt2LLEyYpN2f9oKKi1onGy5XHRSP4BRq2vb` | Token-2022 extensions (no hook program set) |
| Issuer | **Bridge** (Stripe) | metadata uri → `token-metadata.bridge.xyz/solana/cash.json` |

## Key accounts and PDAs

| Account | Address / pattern | Notes |
|---|---|---|
| Operator key | `DDucv2DeUsTsg1rfAcWAnUSUVpqfdHEzxX66ARB2JYVg` | Automated bot — creates, resolves, pays, closes every market (6,000+ sigs/min). Not a PDA; the sole resolution signer. |
| User settings PDA | one per trader, 113 B, disc `93e578389e564dd1` | Owner wallet at offset 8. **29,674** existed on 2026-09-11 — a chain-derived floor on wallets that have ever traded World. |
| Event authority | `3szuQmavzLtzPitk9LbuUtcRd6W3299f7zNGNKD5vK82` | prediCt `__event_authority` (Anchor event-CPI) |
| Per-market authority | Market PDA (per market) | One PDA per market = mint + permanent-delegate + close + metadata-update authority for that market's YES/NO mints. Seed derivation computed in-program → not recovered. |
| Outcome mints | YES/NO Token-2022 pair per market, 6 decimals | Name/symbol in tokenMetadata ext; uri `m.world.xyz/<mint>` (404s once closed). Example: `4mQhMnqNYWwY3XLFcFFVtuCCzRtSwbw5THLGvkLZmAA8` = "ARG vs EGY: ARG wins (YES)". Closed on settlement. |

## Not World — the CASH↔USDC/SOL ramp

DFlow also routes CASH↔USDC/SOL through general Solana DEXs (Jupiter, Raydium, Orca,
Meteora, PumpSwap, pump.fun, Manifest). None are prediction-market machinery — they
price the stablecoin ramp only. Full list in [`docs/reference.md`](docs/reference.md#peripheral-liquidity-not-world--the-cashusdcsol-onoff-ramp).
