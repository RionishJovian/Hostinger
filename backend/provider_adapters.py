"""Provider-neutral callback verification helpers.

The trusted Telegram/Discord adapter must authenticate the platform user first,
then use this verifier before forwarding a decision to the review API.
"""
import hashlib,hmac,time

class CallbackVerificationError(ValueError):pass

def verify_signed_callback(raw_body:bytes,signature:str,timestamp:str,nonce:str,secret:bytes,now:int|None=None,max_age:int=300):
 if not signature or not timestamp or not nonce:raise CallbackVerificationError('Missing callback signature fields')
 try:stamp=int(timestamp)
 except ValueError:raise CallbackVerificationError('Invalid callback timestamp')
 current=int(time.time()) if now is None else now
 if abs(current-stamp)>max_age:raise CallbackVerificationError('Callback timestamp is outside the acceptance window')
 if len(nonce)<16 or len(nonce)>160:raise CallbackVerificationError('Invalid callback nonce')
 expected=hmac.new(secret,timestamp.encode()+b'.'+nonce.encode()+b'.'+raw_body,hashlib.sha256).hexdigest()
 if not hmac.compare_digest(expected,signature.lower()):raise CallbackVerificationError('Invalid callback signature')
 return {'timestamp':stamp,'nonce':nonce,'signature':expected}
