"""Build prediCt split/merge instructions for a self-serve (user-signed) call.

Roster verified on-chain (grab_split.py) and proven callable by an arbitrary
wallet via simulateTransaction. Account order:
  0 user (signer) | 1 market | 2 CASH mint | 3 YES mint | 4 NO mint
  5 user CASH ATA | 6 vault | 7 user YES ATA | 8 user NO ATA | 9,10 Token-2022
"""
import hashlib
import struct

from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta

PREDICT = Pubkey.from_string("prediCtPZCttYMvm2W3PtxmMxLmT1dtN7riU6Cxh6tM")
TOKEN22 = Pubkey.from_string("TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb")
ATA_PROG = Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")
SYS_PROG = Pubkey.from_string("11111111111111111111111111111111")
CASH_DECIMALS = 6


def disc(name: str) -> bytes:
    return hashlib.sha256(f"global:{name}".encode()).digest()[:8]


def ata(owner: Pubkey, mint: Pubkey) -> Pubkey:
    return Pubkey.find_program_address(
        [bytes(owner), bytes(TOKEN22), bytes(mint)], ATA_PROG)[0]


def create_idempotent(payer: Pubkey, owner: Pubkey, mint: Pubkey) -> Instruction:
    a = ata(owner, mint)
    metas = [AccountMeta(payer, True, True), AccountMeta(a, False, True),
             AccountMeta(owner, False, False), AccountMeta(mint, False, False),
             AccountMeta(SYS_PROG, False, False), AccountMeta(TOKEN22, False, False)]
    return Instruction(ATA_PROG, bytes([1]), metas)  # 1 = CreateIdempotent


def _roster(user, mkt, cash_ata, yes_ata, no_ata):
    return [
        AccountMeta(user, True, True),                                  # 0 user (signer)
        AccountMeta(Pubkey.from_string(mkt["market"]), False, True),    # 1 market
        AccountMeta(Pubkey.from_string(mkt["cash_mint"]), False, True), # 2 CASH mint
        AccountMeta(Pubkey.from_string(mkt["yes_mint"]), False, True),  # 3 YES mint
        AccountMeta(Pubkey.from_string(mkt["no_mint"]), False, True),   # 4 NO mint
        AccountMeta(cash_ata, False, True),                             # 5 user CASH ATA
        AccountMeta(Pubkey.from_string(mkt["vault"]), False, True),     # 6 vault
        AccountMeta(yes_ata, False, True),                              # 7 user YES ATA
        AccountMeta(no_ata, False, True),                               # 8 user NO ATA
        AccountMeta(TOKEN22, False, False),                             # 9
        AccountMeta(TOKEN22, False, False),                             # 10
    ]


def _amount_raw(amount_cash: float) -> int:
    return int(round(amount_cash * 10 ** CASH_DECIMALS))


def split_ix(user: Pubkey, mkt: dict, amount_cash: float) -> Instruction:
    cash_ata = ata(user, Pubkey.from_string(mkt["cash_mint"]))
    yes_ata = ata(user, Pubkey.from_string(mkt["yes_mint"]))
    no_ata = ata(user, Pubkey.from_string(mkt["no_mint"]))
    data = disc("split") + struct.pack("<Q", _amount_raw(amount_cash))
    return Instruction(PREDICT, data, _roster(user, mkt, cash_ata, yes_ata, no_ata))


def merge_ix(user: Pubkey, mkt: dict, amount_cash: float) -> Instruction:
    cash_ata = ata(user, Pubkey.from_string(mkt["cash_mint"]))
    yes_ata = ata(user, Pubkey.from_string(mkt["yes_mint"]))
    no_ata = ata(user, Pubkey.from_string(mkt["no_mint"]))
    data = disc("merge") + struct.pack("<Q", _amount_raw(amount_cash))
    return Instruction(PREDICT, data, _roster(user, mkt, cash_ata, yes_ata, no_ata))
