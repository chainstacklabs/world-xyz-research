# world-xyz-research

Independent technical research on **World** (world.xyz) — the Solana prediction market —
reversed from the deployed programs, on-chain state, and DFlow routing.

> **Mainnet.** World is live on Solana mainnet-beta (launch 2026-07-01; on-chain
> activity from 2026-06-20). Not affiliated with World, world.xyz, Phantom, DFlow, or
> Bridge. Every claim here is reproducible from RPC and cryptographically-verified
> Anchor discriminators; World's / Phantom's own messaging is treated as a claim to verify,
> not ground truth. No warranty.

## What World is

World is a prediction market built into the Phantom wallet and world.xyz: you bet on
event outcomes — a football match, BTC up or down in the next 15 minutes — by buying a
token that pays out $1 if you're right and $0 if you're wrong. Positions sit in your own
wallet as ordinary Solana tokens, and payouts settle in **CASH**, a dollar stablecoin
issued by Bridge (Stripe's stablecoin arm).

It is not one program but a composed system: World's own market program (**prediCt**)
holds the collateral and mints outcome tokens; **market makers** (JanusFI, BisonFI) quote
prices and provide liquidity; the **DFlow** router connects your wallet to the makers; and
CASH is the money layer underneath. Who controls which piece — and what that means for
your position — is the core finding of this research.

## How a bet works

Every market is a pair of tokens: **YES** and **NO**. The program mints them only as
equal pairs — lock 1 CASH, get 1 YES + 1 NO (a *complete set*) — and burns them the same
way. At resolution a winning token redeems for exactly 1 CASH; the losing one goes to
zero. That's the whole on-chain protocol: an exact, fee-free vault with no pricing math
in it.

Prices come from the market makers. When you buy, your CASH goes through DFlow to a
maker, which mints a complete set, hands you the side you bet on, and keeps the other.
The price you pay is the market's probability for your outcome — 0.25 CASH per YES token
means the market says 25%. The maker prices the two sides to sum slightly above $1; that
gap is its fee. **The size of that take is not fixed** — it is a per-fill parameter set
by whoever builds the transaction, and has been observed from ~0% up to ~8% of the stake;
see [the fee note](docs/reference.md#worked-trade-decode-price-and-fee).

You are not locked in until resolution — outcome tokens are ordinary tokens with a
continuous maker on the other side, so you can sell back to CASH anytime. The wallet's
cash-out flow pays the sell's proceeds to an account outside your wallet — self-custody
ends at that boundary. When the market resolves, World's operator pushes the payout to
winners automatically; there is no claim step.

If the model sounds like Polymarket, that's because it mechanically is — with different
liquidity and resolution choices:

| | **World** | **Polymarket** |
|---|---|---|
| Outcome tokens | Solana Token-2022 YES/NO pairs | Ethereum ERC-1155 YES/NO (Gnosis CTF) |
| Collateral | CASH (Bridge/Stripe stablecoin) | USDC |
| Price formation | market maker quotes, mints sets on demand | order book (off-chain book, on-chain settle) |
| Trading fee | variable, integrator-set; ~0–8% of stake observed | 0% trading fee (historically) |
| Sell / early exit | yes — swap back to CASH anytime | yes — sell on the book anytime |
| Payout | operator pushes CASH to winners | claim/redeem yourself |
| Resolution | single operator key, no on-chain oracle | UMA optimistic oracle with dispute window |

The full trade decode — real transaction, price and fee math to the raw unit — is in
[`docs/reference.md`](docs/reference.md#worked-trade-decode-price-and-fee).

## Who controls what

- **One automated operator key runs every market's lifecycle** — it creates the market,
  declares the winner, pays the winners, and closes the market down. Resolution is a
  2-byte value that key writes; the instruction carries no oracle account, price feed, or
  proof. World's Chainlink integration (Data Streams + CRE) operates off-chain and feeds
  this key — the chain cannot tell whether an outcome came from Chainlink or from anyone
  else holding the key. There is no dispute window or refund instruction.
- **World owns its main market maker.** JanusFI shares prediCt's upgrade key, so one key
  can rewrite both the market rules and the in-house maker's pricing. BisonFI is
  independently controlled; DFlow is third-party infrastructure.
- **All four programs are upgradeable.** None is immutable.
- **Your tokens are yours, but seizable by design.** Each market's token pair carries a
  *permanent delegate* — the standard Token-2022 mechanism World uses to burn the losing
  side at settlement. The same power means the protocol authority can move or destroy
  positions.
- **CASH belongs to Bridge, not World.** The issuer holds freeze and clawback authority
  over every CASH account, independent of anything World does.

Full analysis, including how World's setup maps to Chainlink's documented integration
patterns, in [`docs/trust-model.md`](docs/trust-model.md).

## Risks

- Outcome integrity rests on one operator key and World's off-chain pipeline — treat it
  as counterparty risk and size positions accordingly.
- Program upgrades can change market rules or maker pricing at any time.
- Positions can be seized or burned by the protocol authority (inherent to settlement).
- CASH collateral can be frozen or clawed back by its issuer.
- A misresolved market has no on-chain recourse.

Severity and mitigations in the [risk table](docs/trust-model.md#risk-summary).

## On-chain vs backend: what each surface can do

A World action is usually not one call — it spans two surfaces. The **on-chain programs**
hold the money and enforce the rules; **off-chain backends** decide what markets exist,
what a trade is worth, and when to resolve, then hand the user a transaction to sign.

**Buying is the clearest case.** It is not a single permissionless contract call — it is
two steps:

1. **Off-chain.** The app asks an order server for a quote. DFlow picks a market maker, which sets the price and the fee and returns a *fully built
   transaction*. Since the web app shipped, this is **open**: World's own
   `aggregator-api-proxy.world-xyz.workers.dev/order` serves fillable outcome-token quotes
   with no API key. (The original survey found this gated; that applied to
   `quote-api.dflow.net` / `dev-quote-api.dflow.net`, which are still key-bound.)
2. **On-chain (permissionless).** The user signs and submits that transaction. It routes
   through the maker into `prediCt.split`, mints a complete set, and hands over one leg.
   *Anyone* can submit this half — the program enforces no maker allowlist.

So "permissionless" is true of the on-chain half only — the price and the market catalog
are still decided off-chain, even though they are now readable by anyone. The exception:
you can skip the off-chain
surface entirely and call `prediCt.split` yourself — verified permissionless on mainnet,
at a true 1.0 basis, no maker and no API key ([`selfserve/`](selfserve/)).

### On-chain — the programs

Who calls each instruction on mainnet. Details in [`docs/reference.md`](docs/reference.md).

| Action | Instruction | Who can call | Off-chain half |
|---|---|---|---|
| **Buy** (mint set, take one leg) | maker CPI → `split` | anyone can submit; maker-routed in practice | DFlow `/order` builds the tx + maker quote |
| **Sell / exit early** | swap → `merge` / transfer | anyone | DFlow `/order` (reverse) |
| **Split / merge directly** | `split` / `merge` | **any wallet** — verified, 1.0 basis | none — pure on-chain, bypasses the spread |
| **Hold / transfer positions** | Token-2022 transfer | anyone — but the per-market permanent delegate can seize | none |
| **Create a market** | `initialize_market` | operator key only | World's off-chain automation triggers it |
| **Resolve** | `determine_outcome` | operator key only | Chainlink Data Streams + CRE compute the outcome off-chain |
| **Pay winners** | `redeem_outcome_for_user` | operator (pushed to you) | operator's automation triggers it |
| **Close a market** | `close_market` | operator key only | operator's automation triggers it |
| **Read any state** | `getAccountInfo` / `getProgramAccounts` | anyone | backends index a subset |

### Off-chain — the backends

What runs off-chain, and what's reachable. Endpoint detail and reproduce steps
in [`docs/reference.md`](docs/reference.md#off-chain-surfaces). Verified 2026-09-11.

| Surface | Host | Role | Access |
|---|---|---|---|
| World frontend | `world.xyz` | Full React SPA | open |
| Market catalog | `markets-api-proxy.world-xyz.workers.dev/api/v1/markets` | 4,000 markets with live bid/ask, volume, open interest, rules, and the on-chain `marketLedger`/`yesMint`/`noMint` | **open, no key** |
| Trade quotes & tx build | `aggregator-api-proxy.world-xyz.workers.dev/order` | Maker RFQ quote + constructed swap tx; carries the platform fee | **open, no key** |
| World backend | `api.world.xyz` | Not the path the web app uses | **gated** (Cloudflare 403) |
| Outcome-token metadata | `m.world.xyz/<mint>` | Per-market name/symbol JSON | open per mint (404s once a market closes) |
| Trade quotes (DFlow direct) | `quote-api.dflow.net` `GET /order` | Same surface, DFlow-hosted | **gated** (`x-api-key`, approval) |
| Resolution data | Chainlink Data Streams + CRE | Prices / match outcomes feeding the operator key | off-chain pipeline |

## What's in this repo

- [`docs/reference.md`](docs/reference.md) — the technical reference: contract inventory,
  CPI graph, recovered prediCt instruction set + discriminators, account layouts, handler
  arithmetic, decoded trade, DFlow, open questions.
- [`docs/trust-model.md`](docs/trust-model.md) — what you're trusting: resolution,
  upgradeability, seizability, the Bridge-stablecoin layer, risk table.
- [`ADDRESSES.md`](ADDRESSES.md) — every address the research relies on, with role and
  verification method.
- [`world_idls/`](world_idls/) — on-chain IDLs (DFlow publishes; prediCt/Janus/Bison do not).
- [`tools/`](tools/) — Python that reproduces every on-chain claim (read-only; no keys).
- [`selfserve/`](selfserve/) — wallet-signing scripts that transact directly with the
  protocol (swap, split, merge, sweep). These **sign and broadcast real mainnet txs**;
  they demonstrate that split/merge are permissionless.

## Reproduce

```bash
cp .env.example .env        # set SOL_RPC (Solana mainnet archive)
uv sync
uv run tools/verify_program.py                # program → ProgramData → upgrade authority
uv run tools/fetch_idl.py DF1ow4tspfHX9JwWJsAb9epbkA8hmpSEAtxXy1V27QBH   # DFlow IDL
uv run tools/map_predict.py 60                # recover prediCt instruction set from logs
uv run tools/classify_ix.py DetermineOutcome  # show resolution has no oracle account
```

## Scope

Primarily read-only reverse-engineering and documentation. The one exception is
[`selfserve/`](selfserve/), wallet-signing scripts that transact directly to verify the
permissionless split/merge finding; they never generate or hold a key and simulate before
sending. Bytecode disassembly (maker pricing curve, PDA seeds, event payloads) is out of
the current scope — see [open questions](docs/reference.md#open-questions).
