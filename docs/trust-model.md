# World trust model

What you are trusting when you hold a World position. Every claim below is decoded from
mainnet transactions and account state; instruction-level detail lives in
[reference.md](reference.md). Verified: 2026-07-09.

Short version: World is **non-custodial for your tokens but not trustless for outcomes**.
Your position lives in your own wallet, but a single operator key decides who wins with no
on-chain oracle, and every program in the path is upgradeable.

## 1. Resolution is a single operator key; Chainlink operates off-chain

World describes settlement as "Chainlink Data Streams + CRE auto-settlement." On-chain,
no Chainlink account appears in World's transactions — not in resolution, not in pricing.

The resolve instruction, `determine_outcome`, carries four accounts and a 10-byte payload
— a u16 outcome the signer writes, with no Chainlink account, verifier CPI, price feed,
signed report, or proof (full roster in
[reference.md](reference.md#determine_outcome-disc-18716d52-4-accounts--resolution)). A
real Chainlink Data Streams report is hundreds of bytes verified by CPI to the verifier
program passing Verifier + AccessController + Config accounts; none of that is present.

The signer is always `DDucv2DeUsTsg1rfAcWAnUSUVpqfdHEzxX66ARB2JYVg` — a single signer
across every `determine_outcome`. It is not a human clicking buttons: it is a
high-frequency automated key (6,000+ signatures within a few minutes of scanning) that
also runs `initialize_market`, `update_metadata`, `redeem_outcome_for_user`, and
`close_market`. One automated key runs the entire market lifecycle: create → resolve →
pay winners → close.

**Where Chainlink sits: off-chain.** The Chainlink Data Streams verifier is live on
Solana mainnet (`Gt9S41PtjR58CbG9JhJ3J6vxesqrNAswbWYbLNTMZA3c`, executable); World does
not call it. It never appears in prediCt transactions; the resolver key
invokes only ComputeBudget and prediCt across all its activity. So Chainlink Data
Streams (prices, FIFA outcomes) and the CRE workflow run entirely off-chain; the CRE's
output is submitted as a plain signed transaction by the operator key. The chain has no
way to tell whether an outcome came from Chainlink or from anyone else with that key. No
challenge window, dispute path, or refund instruction exists in the current program.

Net: the *settlement transaction* lands on-chain; the *oracle and resolution logic* run
off-chain and are not verified on-chain — outcome integrity rests on World's off-chain
pipeline and the operator key. Reproduce:
`uv run tools/classify_ix.py DetermineOutcome` (4 accounts, no oracle) and the verifier /
program scans in this repo's tooling.

### How this maps to Chainlink's documented integration patterns

Checked against Chainlink's own docs — "no on-chain feed" alone is normal for pull-based
products:

- **Data Streams is pull-based; having no persistent on-chain price account is normal
  and expected.** Chainlink documents two valid ways to consume a report: retrieve it
  off-chain (REST/WS/SDK), or verify it on-chain via CPI to the verifier. Off-chain
  retrieval is a legitimate, documented pattern. So World not maintaining a price feed
  account is fine on its own.
- **But on-chain verification is specifically what provides the guarantees.** Chainlink's
  docs are explicit: verifying the report on-chain gives "cryptographic guarantees about
  data accuracy" and confirms "the DON agreed on and signed the data," enabling
  *trust-minimized settlement*. Off-chain-only consumption lacks those guarantees.
- **CRE's intended security is a DON-signed report delivered to a consumer contract.** The
  docs describe the report as a "DON-signed package"; the consumer is meant to receive/verify
  it, so the on-chain result is cryptographically tied to the DON's BFT consensus — not to
  any single key.

What World does relative to that: `determine_outcome` receives no DON-signed report, no
signatures, no verifier CPI, no forwarder/consumer verification — just a 2-byte outcome
from one operator key, submitted as a plain top-level instruction. So World uses the
*permitted off-chain consumption style* but omits **both** trust-minimizing mechanisms
(the Data Streams verifier CPI **and** the CRE signed-report-to-consumer pattern).

**The resolver key is World's protocol operator, not a Chainlink DON transmitter.** The
behavior does not match a DON transmitter address:

- It performs the entire protocol lifecycle — `initialize_market`, creating the outcome
  mints, `update_metadata`, `redeem_outcome_for_user`, `burn_worthless_outcome`,
  `close_market` — with `determine_outcome` only ~5% of its instructions. A DON
  transmitter only transmits signed reports; it does not create markets,
  mint tokens, or redeem on users' behalf.
- It is a single fixed signer; a Solana DON writes via a rotating committee of
  transmitter keys through an OCR2/forwarder program.
- It pays rent to create markets/mints from its own balance and reclaims it on close —
  protocol-treasury behavior, not oracle behavior.
- It invokes only ComputeBudget and prediCt — no OCR2, no forwarder, no verifier, no
  Chainlink program of any kind.

Reproduce: pull `DDucv2De…` transactions and tally instructions/programs.

**Summary:** Chainlink very likely powers the resolution **data** off-chain — a valid,
documented Data Streams/CRE integration. The design omits the on-chain verification step:
the chain cannot confirm an outcome came from Chainlink rather than from whoever holds the
operator key, so settlement carries the guarantees of World's off-chain pipeline plus that
key rather than Chainlink's cryptographic guarantees. The precise description is:
*Chainlink drives resolution off-chain; the on-chain settlement is authorized by a single
World key without Chainlink verification.*

## 2. Every program in the path is upgradeable

None of the four programs is immutable:

| Program | Upgrade authority | Controlled by |
|---|---|---|
| prediCt (market logic, split/merge/settle) | `6YrRV52…Kj7b` | World |
| JanusFI (market maker) | `6YrRV52…Kj7b` | **World (same key)** |
| BisonFI (market maker) | `6dDjBZ…YipS` | independent third party |
| DFlow (router) | `9uo2iJ…wgsh` | DFlow (third-party infra) |

The market logic and the primary market maker share one upgrade key — World can change the
split/merge/settlement rules **and** the maker's pricing at once. A trader has no on-chain
guarantee the curve or payout is stable across upgrades. BisonFI being independently
controlled means at least one maker is not World; DFlow routing is external.

## 3. Outcome tokens are seizable — that is the settlement mechanism

Each market's YES/NO mints set `permanentDelegate` + `mintCloseAuthority` to the market
authority PDA ([details](reference.md#outcome-tokens)). Token-2022 warns on every
transfer: `Mint has a permanent delegate, so tokens in this account may be seized at any
time`. This is how settlement works — `close_market` burns the losing side and closes the
mint. The same power means positions are not immutable holdings; the protocol authority
can move or destroy them. Rent from closed markets is reclaimed by the operator.

## 4. CASH is a Bridge stablecoin with standard issuer controls

CASH (`CASHx9…CASH`, Token-2022) is issued via **Bridge**
(Stripe's stablecoin infra — metadata at `token-metadata.bridge.xyz`) and carries:

- **permanent delegate + close authority** `E7Jd…B3qw` — the issuer can seize or burn CASH
  from any account.
- **freeze authority** `AyCP…prY5` — the issuer can freeze any CASH account.
- **confidential-transfer** authority and a **transfer-hook** authority `3etmw…q2vb`
  (no hook program set yet, but the slot is authority-controlled and can be armed).

So beneath World's own trust assumptions sits a fully controllable regulated stablecoin:
the CASH issuer can freeze or claw back the collateral independent of World.

## 5. What you are NOT trusting

- **Custody of your position** — outcome tokens are Token-2022 balances in your own
  wallet, not held by World or Phantom. Confirmed by the `split` account roster (the
  YES/NO recipient token accounts are user-owned).
- **Off-chain price to place a trade** — pricing is a live on-chain swap through DFlow →
  maker; the fill and resulting token balances are all on-chain and verifiable per tx.

## Risk summary

| Risk | Severity | Mitigation |
|---|---|---|
| Single automated operator key resolves all outcomes, no on-chain oracle | High | Cap exposure per market; watch `determine_outcome` signer; treat as counterparty risk |
| All programs upgradeable (curve/payout can change) | High | Re-verify after any deploy-slot change |
| Outcome tokens seizable/burnable (permanent delegate) | Medium | Inherent to settlement; redeem winners promptly |
| CASH issuer (Bridge) freeze/clawback | Medium | External to World; standard regulated-stablecoin risk |
| No refund/dispute instruction | Medium | No recourse if a market is misresolved |
