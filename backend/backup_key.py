"""Purpose-bound Fernet keys derived from the deployment backup key.

The backup key may be a Fernet key or any base64 value of at least 32 random
bytes (for example `openssl rand -base64 48`).
"""
import base64,binascii
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

def master_key(raw):
 if isinstance(raw,bytes):raw=raw.decode('ascii','ignore')
 value=(raw or '').strip().replace('-','+').replace('_','/')
 try:master=base64.b64decode(value+'='*(-len(value)%4),validate=True)
 except (binascii.Error,ValueError):return None
 return master if len(master)>=32 else None

def derived_fernet(raw,info):
 master=master_key(raw)
 if master is None:return None
 return Fernet(base64.urlsafe_b64encode(HKDF(algorithm=hashes.SHA256(),length=32,salt=None,info=info).derive(master)))
