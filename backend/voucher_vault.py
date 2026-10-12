"""Encrypted voucher codes for router provisioning.

The normalized code becomes the MikroTik HotSpot username, so it must be pushed
again to routers that were offline, replaced or added later. It is sealed with
a key derived from the backup key, bound to the business, and never returned
by any API after issue.
"""
import base64,os
from cryptography.fernet import Fernet,InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

INFO=b'mikromagic-voucher-code-v1'

def _cipher():
 raw=os.environ.get('MIKROMAGIC_BACKUP_KEY','')
 try:master=base64.urlsafe_b64decode(raw.encode())
 except (ValueError,TypeError):return None
 if len(master)!=32:return None
 return Fernet(base64.urlsafe_b64encode(HKDF(algorithm=hashes.SHA256(),length=32,salt=None,info=INFO).derive(master)))

def seal(tenant_id,code):
 """Return the sealed code, or None when no key is configured (the voucher then cannot sync)."""
 cipher=_cipher()
 return cipher.encrypt(f'{tenant_id}:{code}'.encode()).decode() if cipher else None

def unseal(tenant_id,token):
 cipher=_cipher()
 if not cipher or not token:return None
 try:value=cipher.decrypt(token.encode()).decode()
 except (InvalidToken,UnicodeDecodeError):return None
 owner,_,code=value.partition(':')
 return code if owner==tenant_id and code else None
