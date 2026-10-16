"""Frozen-v1 voucher code rules.

Codes are case-insensitive; spaces and hyphens are ignored. New codes are an optional
SME prefix plus a secure 6-character suffix without confusing characters (O/0, I/1).
VIP packages may use a fully custom code. Hashes are scoped to the business, so equal
codes in two businesses never collide or reveal each other. Codes issued before this
rule (26-character base32, unscoped hash) keep working unchanged.
"""
import hashlib,re,secrets
from fastapi import HTTPException
from sqlalchemy import select
from .models import Voucher

SUFFIX_ALPHABET='ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
SUFFIX_LENGTH=6
PREFIX_MAX=8
CUSTOM_MIN,CUSTOM_MAX=6,32
HINT_LENGTH=2
GENERATION_ATTEMPTS=8

def normalize(value):return re.sub(r'[\s-]+','',value or '').upper()
def valid_redeemable(value):return bool(re.fullmatch(r'[A-Z0-9]{6,40}',value))

def normalize_prefix(value):
 prefix=normalize(value)
 if prefix and not re.fullmatch(r'[A-Z0-9]{1,%d}'%PREFIX_MAX,prefix):raise HTTPException(422,f'Prefix must be 1–{PREFIX_MAX} letters or numbers')
 return prefix or None

def normalize_custom(value):
 code=normalize(value)
 if not re.fullmatch(r'[A-Z0-9]{%d,%d}'%(CUSTOM_MIN,CUSTOM_MAX),code):raise HTTPException(422,f'Custom code must be {CUSTOM_MIN}–{CUSTOM_MAX} letters or numbers')
 return code

def scoped_hash(tenant_id,code):return hashlib.sha256(f'voucher-code:v2:{tenant_id}:{code}'.encode()).hexdigest()
def legacy_hash(code):return hashlib.sha256(code.encode()).hexdigest()
def candidate_hashes(tenant_id,code):return [scoped_hash(tenant_id,code),legacy_hash(code)]

def find_voucher(s,tenant_id,code):
 return s.scalar(select(Voucher).where(Voucher.tenant_id==tenant_id,Voucher.code_hash.in_(candidate_hashes(tenant_id,code))))

def display(code,prefix):return f'{prefix}-{code[len(prefix):]}' if prefix else code

def new_code(s,tenant_id,prefix=None,custom=None,exclude=()):
 """Return (normalized code, scoped hash, hint). The caller still relies on the unique hash index for races."""
 if custom:
  if find_voucher(s,tenant_id,custom):raise HTTPException(409,'This code is already used in your business; choose another')
  return custom,scoped_hash(tenant_id,custom),custom[-HINT_LENGTH:]
 for _ in range(GENERATION_ATTEMPTS):
  code=(prefix or '')+''.join(secrets.choice(SUFFIX_ALPHABET) for _ in range(SUFFIX_LENGTH))
  if code not in exclude and not find_voucher(s,tenant_id,code):return code,scoped_hash(tenant_id,code),code[-HINT_LENGTH:]
 raise HTTPException(409,'Could not find an unused code for this prefix; try again or use a different prefix')
