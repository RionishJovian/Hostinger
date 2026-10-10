import unittest,hmac,hashlib
from backend.provider_adapters import verify_signed_callback,CallbackVerificationError

class ProviderAdapterTests(unittest.TestCase):
 def test_valid_signed_callback(self):
  body=b'{"decision":"approved"}';stamp='1000';nonce='nonce-1234567890';secret=b'test-secret';sig=hmac.new(secret,stamp.encode()+b'.'+nonce.encode()+b'.'+body,hashlib.sha256).hexdigest()
  result=verify_signed_callback(body,sig,stamp,nonce,secret,now=1000);self.assertEqual(result['timestamp'],1000)
 def test_rejects_stale_or_tampered_callback(self):
  with self.assertRaises(CallbackVerificationError):verify_signed_callback(b'body','00','1000','nonce-1234567890',b'secret',now=1401)
  with self.assertRaises(CallbackVerificationError):verify_signed_callback(b'body','00','1000','nonce-1234567890',b'secret',now=1000)
 if __name__=='__main__':unittest.main()
