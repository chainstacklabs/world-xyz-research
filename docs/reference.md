# Technical reference

Canonical technical detail for World's on-chain system: contract inventory, the
`prediCt` instruction set, account layouts, handler arithmetic, a decoded trade, and the
DFlow router. Plain-language overview in the [README](../README.md); trust analysis in
[trust-model.md](trust-model.md); addresses with verification method in
[ADDRESSES.md](../ADDRESSES.md).

World publishes no on-chain IDL for `prediCt` or its market makers (the IDL PDA
`ER1es1Xz…WkTZ` is empty). Everything below is decoded from live transactions, program
logs, and Anchor discriminators verified against `sha256("global:<name>")[:8]`. Each
section carries its reproduce command. Verified: 2026-07-09/10 (mainnet).

## Contract inventory

### World core

| Contract | Address | Role | Control |
|---|---|---|---|
| **prediCt** | `prediCtPZCttYMvm2W3PtxmMxLmT1dtN7riU6Cxh6tM` | Market program: mint/burn outcome-token complete sets (`split`/`merge`), resolve (`determine_outcome`), pay (`redeem_outcome_for_user`), close (`close_market`). Anchor, IDL withheld, emits Anchor events. | upgrade `6YrR…Kj7b` (World); operated by key `DDucv2De…` |
| **JanusFI** | `JanusXpm3gsW3c9ErNoUgHppL8dGLvZKB7uekkJEYFP` | Market maker AMM. CPIs `prediCt.split/merge` to fill trades. No IDL. | upgrade `6YrR…Kj7b` — same key as prediCt → World's own MM |
| **BisonFI** | `2DNbzPochEcyCcWMbL4d9S3u9QqQEj5bbe6cSZFvKsbh` | Market maker AMM. Also CPIs `prediCt.split/merge`. No IDL. | upgrade `6dDj…YipS` — independent third party |
| **BiSoNH** | `BiSoNHVpsVZW2F7rx2eQ59yQwKxzU5NvBcmKshCSUypi` | Second Bison program (same team, upgrade `6dDj…YipS`). Spot-swap venue on the pay-in ramp: executes SOL→USDC→CASH conversion legs inside DFlow routes ahead of the prediction leg. Legacy SPL Token; never CPIs prediCt. Details in [Peripheral liquidity](#peripheral-liquidity-not-world--the-cashusdcsol-onoff-ramp). | `6dDj…YipS` |
| **CASH mint** | `CASHx9KJUStyftLFWGvEVf59SGeG9sh5FfcnZMVPCASH` | Collateral. Token-2022, Bridge-issued stablecoin. Not a program. | Bridge authorities (see [trust-model.md](trust-model.md)) |

Only JanusFI and BisonFI (`2DNbz`) call `prediCt` to mint outcome tokens — the
outcome-token maker set is those two.

### Routing (external infrastructure)

| Contract | Address | Role |
|---|---|---|
| **DFlow orchestrator** | `DF1ow4tspfHX9JwWJsAb9epbkA8hmpSEAtxXy1V27QBH` | RFQ router / entrypoint (`swap`, `swap_with_destination`). Anchor IDL published. Routes prediction orders to Janus/Bison and CASH-ramp orders to general DEXs. Third-party (upgrade `9uo2…wgsh`). |

### Peripheral liquidity (not World — the CASH↔USDC/SOL on/off-ramp)

DFlow aggregates general Solana liquidity for moving between CASH and USDC/SOL:
Jupiter v6 (`JUP6Lk…`), Raydium CLMM (`CAMMCzo5`), Raydium AMM v4 (`675kPX9`), Raydium CPMM
(`cpamdp…`), Orca Whirlpool (`whirLbMi`), Meteora DLMM (`LBUZKhRx`), PumpSwap (`pAMMBa…` +
fee `pfeeUx…`), pump.fun (`6EF8rr…`), Manifest (`MNFSTq…`), plus `ALPHAQ…`, `TessVd…`,
`AQU1FR…`, `9H6tua…`. None are prediction-market machinery — they price the stablecoin
ramp only.

Bison's own `BiSoNH…` program also serves this ramp: a single BiSoNH instruction can
convert SOL→USDC→CASH end to end, or take only the SOL→USDC leg with `ALPHAQ…` finishing
USDC→CASH. The ramp composes with the prediction leg in one atomic transaction — a buyer
can pay in SOL and never hold CASH.

### CPI relations

```
user (Phantom)
  │  swap | swap_with_destination
  ▼
DFlow  DF1ow…  ──┬─ prediction leg ─→ JanusFI / BisonFI ──→ prediCt.split|merge
                 │                                            │  (mint/burn YES+NO set vs CASH)
                 │                                            ├─→ Token2022 (mint/transfer/burn)
                 │                                            ├─→ System (alloc)
                 │                                            └─→ prediCt (event-CPI, emit)
                 └─ CASH ramp leg ─→ BiSoNH / ALPHAQ / Jupiter / Raydium / Orca / Meteora / PumpSwap / pump.fun / Manifest

operator key  DDucv2De…  ──→ prediCt.{initialize_market, determine_outcome,
                               redeem_outcome_for_user, close_market, update_metadata}
```

CPI edges: `AToken→Token2022`, `prediCt→Token2022` (112), `prediCt→prediCt`
(28, event-CPI), `JanusFI→prediCt` (6), `BisonFI→prediCt` (8), `DFlow→{JanusFI,BisonFI,
Meteora,PumpSwap,Raydium,Orca,…}`, `DFlow→DFlow` (138, internal). The Chainlink Data
Streams verifier: 0 edges anywhere. Reproduce: `uv run python tools/map_relations.py`.

## prediCt instruction set

Twelve instructions, all matching `sha256("global:<snake_name>")[:8]` — an Anchor program
with a withheld IDL. `split`/`merge`/`*_user_settings` appear as inner instructions;
`initialize_market`/`determine_outcome`/`close_market`/`update_metadata` as top-level.
Reproduce: `uv run tools/map_predict.py 60`.

| Instruction | Anchor discriminator | Accts | Role |
|---|---|---|---|
| `initialize_market` | `2323bdc19b30aacb` | 11 | Create a market: new 320-byte Market PDA + YES/NO Token-2022 mints (supply 0) + CASH vault |
| `split` | `7cbd1b2bd8289342` | 11 | Mint an equal YES+NO complete set, moving CASH into the market vault |
| `merge` | `948dec2fae7e456f` | 11 | Burn a YES+NO set back into CASH |
| `determine_outcome` | `1871166631956d52` | 4 | Resolve — write the winning side (u16 0–10000). No oracle account (see below) |
| `redeem_outcome_for_user` | `0011a762e91c6b34` | — | Payout — operator redeems a winner's tokens for CASH on their behalf |
| `burn_worthless_outcome` | `b080ce016e205a2d` | — | Post-resolution: burn losing-side tokens (no CASH out) |
| `close_market` | `589af8ba300e7bf4` | 11 | Post-settlement: burn/close outcome mints + vault + Market, reclaim rent |
| `close_empty_outcome_account` | `78b0898a12824073` | — | Close a drained outcome token account |
| `update_metadata` | `aab62bef614ee1ba` | 4 | Update an outcome mint's Token-2022 metadata |
| `create_user_settings` | `aad9c4bd2a7fe4c9` | 4 | Per-user settings PDA |
| `update_user_settings` | `3a2689e8ec5dafea` | 3 | " |
| `close_user_settings` | `1188a5b29e74ad65` | 3 | " |

The program uses the Anchor event-CPI pattern — the `__event_authority` PDA
`3szuQmavzLtzPitk9LbuUtcRd6W3299f7zNGNKD5vK82`
(`find_program_address([b"__event_authority"])`) appears as a self-CPI signer
(discriminator `e445a52e51cb9a1d`), so the program emits structured Anchor events, not
just log strings. Payload layout not yet decoded (see [Open questions](#open-questions)).

## Handler arithmetic

Read directly from the Token-2022 MintTo/Burn/Transfer amounts each handler performs (only
prediCt holds the outcome mints' authority, so its mints/burns are unambiguous). The
amounts match exactly, to the raw unit. Reproduce:
`uv run python tools/decode_handler.py <Split|Merge|RedeemOutcomeForUser|BurnWorthlessOutcome>`
— it pulls fresh live transactions, so the claim re-verifies against current mainnet on
every run.

| Handler | Effect |
|---|---|
| `split(N)` | lock **N** CASH → mint **N** YES + **N** NO |
| `merge(N)` | burn **N** YES + **N** NO → release **N** CASH |
| `redeem_outcome_for_user(N)` (winner) | burn **N** winning tokens → pay **N** CASH |
| `burn_worthless_outcome(N)` (loser) | burn **N** losing tokens → **0** CASH |
| `determine_outcome(o)` | write winning side, `o` ∈ {0, 10000}; no token movement |

The protocol is a pure, fee-free conditional-token vault (the Gnosis-CTF invariant):

```
1 CASH  ⇔  1 YES + 1 NO          (split / merge, exact, reversible)
at resolution:  winning token → 1 CASH,  losing token → 0
```

Every operation conserves value 1:1 — the vault always holds exactly one CASH per
outstanding complete set, and at settlement winners drain their share while losers burn to
nothing, netting the vault to zero with no protocol-level fee or leakage. The program
contains no pricing math at all; all price formation and the ~2% spread happen off-chain
in the market maker's quote (see [Worked trade decode](#worked-trade-decode-price-and-fee)).

## Market lifecycle

1. **`initialize_market`** — operator creates Market PDA + YES/NO mints + CASH vault.
2. **`split` / `merge`** — complete sets are minted/burned as users trade; users hold one
   leg as a Token-2022 balance in their own wallet. In practice the maker CPIs these, but
   they are permissionless (see [below](#splitmerge-are-permissionless)).
3. **`determine_outcome`** — operator writes the winning side (no on-chain oracle).
4. **`close_market`** — operator burns the losing side, closes mints + vault + Market,
   reclaims rent; winners' tokens redeem 1:1 for CASH via `redeem_outcome_for_user`.

The full lifecycle — create → trade → resolve → pay → close — is run by a single automated
operator key (`DDucv2De…`); analysis in [trust-model.md](trust-model.md). Resolved markets
are actively torn down, which is why most historical markets return `null` on
`getAccountInfo` while their transaction history persists (the mint's `m.world.xyz/<mint>`
metadata uri 404s once closed too).

## Account rosters

### `split` (disc `7cbd…9342`, 11 accounts) — complete-set mint

| # | Role (inferred) |
|---|---|
| 0 | JanusFI market/pool state account (owner = JanusFI program, ~400 B) |
| 1 | **Market** state account (owner = prediCt, 320 B) |
| 2 | CASH mint |
| 3 | YES outcome mint (Token-2022) |
| 4 | NO outcome mint (Token-2022) |
| 5 | CASH token account owned by the JanusFI pool |
| 6 | CASH vault owned by the Market PDA (collateral) |
| 7 | YES token account (recipient) |
| 8 | NO token account owned by the JanusFI pool |
| 9,10 | Token-2022 program |

After a `split` the YES and NO mints carry equal supply — the defining property of
complete-set minting. `merge` is the mirror image (11 accounts, same roster) and burns the
pair back to CASH — post-merge supplies stay near-equal, drifting only by the amount held
one-sided by traders.

### `determine_outcome` (disc `1871…6d52`, 4 accounts) — resolution

| # | Role |
|---|---|
| 0 | **signer** = `DDucv2DeUsTsg1rfAcWAnUSUVpqfdHEzxX66ARB2JYVg` (World operator key) |
| 1 | Market state account (320 B) |
| 2 | event-authority PDA `3szuQma…` |
| 3 | prediCt program |

Instruction data is 10 bytes: the 8-byte discriminator + a u16 outcome (0–10000), written
as `0` (NO wins) or `10000` (YES wins). There is no Chainlink account, price feed,
oracle, or proof in the resolution instruction — the outcome is a value written by the
operator signer. What that means for trust, and where Chainlink actually sits, is analyzed
in [trust-model.md](trust-model.md). Reproduce:
`uv run tools/classify_ix.py DetermineOutcome`.

### `initialize_market` / `close_market`

`initialize_market` (signer = the operator key `DDucv2De…`) allocates the 320-byte Market
PDA, both outcome mints (Token-2022 with `mintCloseAuthority` + `permanentDelegate` set to
the market authority, supply 0), and the Market's CASH vault. `close_market` (same signer)
tears the market down after settlement — closing the outcome mints, the vault, and the
Market account, reclaiming rent.

## Market account layout

Decoded by capturing live (open) 320-byte Market accounts from recent `split` rosters,
locating known pubkeys per offset, and decoding `initialize_market` instruction data.
Reproduce: `uv run tools/decode_market.py`.

### Market account (prediCt-owned, 320 bytes, disc `dbbed53700e3c69a`)

| Offset | Bytes | Field | Verified |
|---|---|---|---|
| 0 | 8 | Anchor discriminator `dbbed53700e3c69a` | ✓ |
| 8 | 32 | creator / operator = `DDucv2De…` | ✓ (matches operator key) |
| 40 | 32 | CASH mint (collateral) | ✓ |
| 72 | 32 | YES outcome mint | ✓ |
| 104 | 32 | NO outcome mint | ✓ |
| 136 | 32 | CASH vault (collateral token account) | ✓ |
| 168 | ~32 | config/params (contains small ints, e.g. `0xfffffd`, a slot-like `~93.8M`) | partial |
| ~200 | 1+32 | flag byte + 32-byte market/condition id (same blob echoed in init data) | inferred |
| ~256 | 8+8 | start / end timestamps in **milliseconds** (≈`1.7836e12`; ~15-min window) | ✓ from init data |
| tail | | resolved flag + winning outcome (u16 0/10000); all-zero while open, written by `determine_outcome` | inferred |

Reading offsets 8–168 decodes any live market's collateral, outcome mints, and vault
directly from chain. Resolved/outcome fields only populate at settlement, and the account
is closed shortly after (`close_market`) — hence the `inferred` rows above (see
[Open questions](#open-questions)).

The Market PDA is its own outcome-mint authority: market address == YES/NO mint authority
== permanent delegate == close authority == metadata update authority.

### `initialize_market` instruction data (disc `2323bdc19b30aacb`, ~296 B)

```
disc(8) | id/nonce(8) | flag(1)+market_id(32) | start_ms(u64) | end_ms(u64)
        | YES: len+name, len+symbol, len+uri
        | NO:  len+name, len+symbol, len+uri
```

Names/symbols run like "BTC Up" / `BTC-UP`, uris `https://m.world.xyz/<mint>`
where `<mint>` is the corresponding YES/NO mint address (matching instruction accounts
[3]/[4]). Outcome names, symbols, and metadata URIs are chosen off-chain and passed in
verbatim at creation. Reproduce: `getTransaction` on any recent `initialize_market` tx
signed by the operator key and parse the data per the format above.

### Account relations (owners established; seeds not derived)

| Account | Owner | Per | Status |
|---|---|---|---|
| Market state (320 B) | prediCt | market | owner confirmed; layout above; **seed open** |
| YES / NO outcome mints (Token-2022) | Token-2022 | market | confirmed; authority = per-market PDA |
| per-market authority | — (PDA) | market | is the Market PDA itself (mint+delegate+close+metadata auth) |
| CASH vault (ATA) | market PDA | market | confirmed via split/merge rosters |
| JanusFI/BisonFI pool state (~400 B) | maker program | market | owner confirmed; **layout open** |
| user settings PDA | prediCt | user | exists (create/update/close ix); **seed + fields open** |
| event authority PDA `3szuQma…` | — | global | confirmed = `__event_authority` |

## Outcome tokens

Token-2022, 6 decimals. Name/ticker in the `tokenMetadata` extension, e.g.
`4mQhMnq…mAA8` → name "ARG vs EGY: ARG wins (YES)", symbol `ARGwEGY-Y`, uri
`https://m.world.xyz/<mint>`. Each market's YES+NO mints share a single authority PDA (the
Market PDA) that is simultaneously mint + permanent-delegate + close + metadata-update
authority — this is how `prediCt` settles: it can seize (permanent delegate) and burn the
losing side and close the mint. Token-2022 emits `Warning: Mint has a permanent delegate,
so tokens in this account may be seized at any time` on every transfer.

## split/merge are permissionless

`split` and `merge` are callable by any wallet, not only by JanusFI/BisonFI. The maker
appears on these instructions because Phantom's frontend routes trades through it, not
because `prediCt` requires it — a routing convention, not on-chain access control.

The program's only constraints on the caller are that it **signs** and **owns the CASH
source account** (account 5's token-owner must equal the signer at account 0, which the
Token-2022 `TransferChecked` enforces). Nothing ties the caller to a registered maker:

- The Market account stores creator, mints, and vault (offsets 40/72/104/136) — no maker
  or pool field — so there is no `has_one` to bind the caller.
- `split`/`merge` receive exactly 11 accounts, all identified; none is a config, registry,
  or allowlist PDA. Anchor can only enforce constraints on accounts an instruction
  receives, so no maker-allowlist check is even expressible here.

The mints and vault passed must be the target market's own, and the market must be open
(resolved markets are `close_market`'d, so their mints/vault no longer exist).

**Consequence.** A user can mint a complete set (`split`) and redeem it (`merge`) directly,
at a true 1.0 basis, bypassing the 2–3% spread baked into the maker's quote. Confirmed end
to end on mainnet: 1 CASH splits into 1 YES + 1 NO and the pair merges back to exactly
1 CASH, value-conserving to the raw unit. Reproduce with the wallet-signing scripts
in [`../selfserve/`](../selfserve/) (`split.py` / `merge.py`).

## Worked trade decode: price and fee

There is no pool you bet into and no order book you match against. A market maker (JanusFI
or BisonFI), reached through the DFlow RFQ router, quotes a price and fills your trade by
minting a complete set and keeping the other leg — or, when it already holds the requested
side, by selling straight from inventory with no `split` at all. A real buy decodes to:

| Flow | Amount |
|---|---|
| User pays | **3.531378 CASH** |
| User receives | **14.218261 YES** (`2vbjEjjf…`) |
| Complete set minted → market vault | 14.218261 CASH → 14.218261 YES + 14.218261 NO |
| Maker (JanusFI) funds the rest | 10.993453 CASH in, keeps 14.218261 NO |
| Fees (3 recipients) | 0.306570 CASH |

- **User's price** = 3.531378 / 14.218261 = **0.2484 CASH per YES** — the market prices
  this outcome at ~24.8% probability. A YES token pays 1 CASH if YES wins.
- **Maker's price for NO** = 10.993453 / 14.218261 = **0.7732 CASH per NO** (~77.3%).
- **YES + NO = 0.2484 + 0.7732 = 1.0216.** The 2.16% over $1 is the fee/spread, and it
  equals the fees collected (0.306570 / 14.218261 = 2.16%). Prices summing above 1 is the
  maker's margin — it mints a $1 set and sells the two legs for ~$1.02.

The spread runs 2–3% and splits across three receivers, the second always receiving
exactly one tenth of the first. It is not a separate line item — it is baked into the
quote (why YES+NO > 1).

Reproduce: `getTransaction` on any DFlow buy → sum `preTokenBalances`/`postTokenBalances`
deltas by owner+mint.

## Payout path

At resolution `determine_outcome` writes the u16 outcome. Winners are then paid by the
operator key calling `redeem_outcome_for_user` — it redeems winning tokens for CASH on the
holder's behalf, so payout is pushed to the user with no claim step. `close_market` then
burns the losing side and tears the market down.

Positions are tradeable before resolution: outcome tokens are ordinary Token-2022 balances
with a continuous maker on the other side, so an early exit is a swap back to CASH (the
reverse direction through DFlow): the seller's tokens go to the maker, which pairs them
with its own inventory of the other side and CPIs `prediCt.merge`; the vault releases
1 CASH per pair and the seller is paid net of spread. Reproduce sells: Dune
`dflow_solana.swap_orchestrator_evt_swapevent`, `output_mint` = CASH, `input_mint` ≠ USDC,
since 2026-06-20.

Sell proceeds do not have to land in the seller's wallet — `swap_with_destination` takes
the destination as a parameter, and it can be a token account owned by a different key.
The wallet cash-out flow uses this: a sponsor wallet fronts the seller exactly 0.1 SOL for
fees and rent, the sell pays its CASH to a destination account owned by a separate key
(close authority assigned to a reclaim key), and the seller returns the unspent SOL in a
follow-up transaction. The three transactions land in the same slot, the seller's wallet
nets zero SOL and holds no CASH afterwards — trading is self-custodial, but proceeds leave
self-custody at the cash-out boundary.

## DFlow orchestrator

Anchor `swap_orchestrator` v0.1.0, IDL published on-chain (saved in
[`../world_idls/dflow.json`](../world_idls/dflow.json); reproduce:
`uv run tools/fetch_idl.py DF1ow4tspfHX9JwWJsAb9epbkA8hmpSEAtxXy1V27QBH`). 17
instructions; the ones on the World path: `swap`, `swap_with_destination`,
`swap2_with_destination`, `wrap_sol`/`unwrap_sol`. CASH-funded trades enter as
`swap_with_destination` or plain `swap`; SOL-funded trades as `wrap_sol` + `swap`, with
the ramp legs ([Peripheral liquidity](#peripheral-liquidity-not-world--the-cashusdcsol-onoff-ramp))
in the same transaction. An RFQ order model
(`open_order`/`fill_order`/`close_order`, single `Order` account type) lets market makers
quote off-chain and fill on-chain. IDL authority `DhoSEG…BRW`. DFlow is third-party
infrastructure, not World-controlled (distinct upgrade authority — see
[ADDRESSES.md](../ADDRESSES.md)).

## Off-chain surfaces

A World trade spans two surfaces: the on-chain programs above, and off-chain backends that
hold the market catalog, quote prices, and drive resolution. The backends are gated, so
their existence is verifiable but their contents mostly are not.

### World's own surfaces

- **`world.xyz`** is a thin single-page app — one Vite bundle, no API references in it. The
  real trading UI ships inside **Phantom**, not here. Reproduce:
  `curl -s https://world.xyz/ | wc -c` (≈915 B) and grep the one referenced
  `/assets/index-*.js` for hosts (only `w3.org` / `react.dev` appear).
- **`api.world.xyz`** is World's own backend — the market catalog Phantom renders. It sits
  behind Cloudflare and returns `403` with an empty body on every path and method, so its
  contents are gated. Reproduce:
  `curl -s -o /dev/null -w '%{http_code}' https://api.world.xyz/markets` → `403`.
- **`m.world.xyz/<mint>`** serves each outcome mint's metadata JSON (name/symbol/uri), the
  same uri embedded in the Token-2022 metadata extension. It 404s once a market is closed.

A real Phantom World buy resolves to World's `prediCt…` program: it routes
DFlow → JanusFI → `prediCt.split` (see
[Worked trade decode](#worked-trade-decode-price-and-fee)), and its outcome token carries
`m.world.xyz` metadata.

### DFlow Trading API — the quote surface

Buying/selling through the frontend goes through DFlow's Trading API, which returns a
fully constructed transaction the wallet signs. Docs: `pond.dflow.net` (OpenAPI served at
`quote-api.dflow.net`). Two hosts:

- **`quote-api.dflow.net`** — production, requires an `x-api-key` header (request form,
  2–5 day approval). `403` without a key.
- **`dev-quote-api.dflow.net`** — keyless, rate-limited, "testing only".

World's outcome tokens are Token-2022, and DFlow's own docs state Token-2022 mints must use
**`GET /order`** (which returns a built tx), not the `/intent` declarative path. The
`/order` endpoint carries prediction-market parameters — `isNativePredictionMarketOutput`,
`predictionMarketSlippageBps`, `predictionMarketInitPayer` / `…MustSign`, and
`initPredictionMarketCost` ("cost in lamports to initialize a prediction market … if the
transaction will initialize the prediction market"). So the order server, not the user,
picks the maker, sets slippage, and decides whether the tx also initializes the market.

The keyless dev endpoint returns `{"code":"route_not_found"}` for a live World outcome
mint (both buy and sell directions), so World's makers (JanusFI/BisonFI) quote only on the
gated production endpoint that authorized integrators use. Reproduce (with a live YES mint
from `tools/decode_market.py`):

```bash
curl -s 'https://dev-quote-api.dflow.net/order?inputMint=CASHx9KJUStyftLFWGvEVf59SGeG9sh5FfcnZMVPCASH&outputMint=<liveYES>&amount=1000000&slippageBps=200'
# → {"msg":"Route not found","code":"route_not_found"}
```

## Open questions

Bytecode-level items, out of the current read-only scope:

1. **PDA seed derivations** — Market/YES/NO/vault are confirmed off-curve PDAs, but the
   seed scheme did not match any content-based pattern tried (labels ×
   nonce/mint/counter/timestamp, ATA, counter brute 0–300k). Computed in-program → needs
   disassembly. State is *readable*; address *derivation* is not yet reproducible.
   (Per-market authority solved: it is the Market PDA.)
2. **Maker internals** — how JanusFI/BisonFI price and manage inventory (RFQ quoting is
   off-chain; on-chain only the fill is visible), and the ~400-byte pool state layout.
3. **DFlow RFQ order lifecycle** — the `open_order`/`fill_order`/`close_order` handshake
   (only the fill lands on-chain; the quote round-trip stays off-chain).
4. **Event payloads** — decode prediCt's Anchor event-CPI data for exact per-trade records.
5. **Resolved Market tail layout** — markets close too fast to observe a
   resolved-but-still-open account.
6. **CASH issuance/redemption** — the Bridge side (mint against USD, redemption path).

(BiSoNH role solved: pay-in ramp venue — see [World core](#world-core) and
[Peripheral liquidity](#peripheral-liquidity-not-world--the-cashusdcsol-onoff-ramp).)
