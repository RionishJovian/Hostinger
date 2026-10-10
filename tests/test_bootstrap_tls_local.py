"""REAL localhost TLS transport; synthetic RouterOS JSON, no real router."""
from datetime import datetime,timedelta,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import ipaddress
from pathlib import Path
import ssl
import tempfile
import threading
import unittest
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from backend.routeros_adapter import RouterOSClient,RouterOSCredential,RouterOSError


class LocalTLSAcceptance(unittest.TestCase):
    def test_actual_TLS_accepts_trusted_SAN_rejects_bad_CA_host_and_expiry(self):
        with tempfile.TemporaryDirectory(prefix='mm-tls-') as folder:
            root=Path(folder);now=datetime.now(timezone.utc)
            ca_key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
            name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Synthetic local test CA')])
            ca=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(ca_key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(days=2)).not_valid_after(now+timedelta(days=2)).add_extension(x509.BasicConstraints(ca=True,path_length=0),critical=True).add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()),critical=False).add_extension(x509.KeyUsage(False,False,False,False,False,True,True,None,None),critical=True).sign(ca_key,hashes.SHA256())
            ca_path=root/'ca.pem';ca_path.write_bytes(ca.public_bytes(serialization.Encoding.PEM));ca_path.chmod(0o600)
            class Handler(BaseHTTPRequestHandler):
                def do_GET(self):
                    body=b'[{"version":"7.24.2","architecture-name":"arm64"}]'
                    self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
                def log_message(self,*args):pass
            def endpoint(hostname,expired=False):
                key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
                cert=x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,hostname)])).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(days=1)).not_valid_after(now-timedelta(hours=1) if expired else now+timedelta(days=1)).add_extension(x509.SubjectAlternativeName([x509.DNSName(hostname)]),critical=False).add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),critical=False).sign(ca_key,hashes.SHA256())
                cert_path=root/'leaf.pem';key_path=root/'key.pem'
                cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM));cert_path.chmod(0o600)
                key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()));key_path.chmod(0o600)
                context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(cert_path,key_path)
                server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.socket=context.wrap_socket(server.socket,server_side=True)
                thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
                return server,thread,'https://localhost:'+str(server.server_port)
            for hostname,expired,trust,success in [('localhost',False,True,True),('localhost',False,False,False),('wrong.invalid',False,True,False),('localhost',True,True,False)]:
                server,thread,url=endpoint(hostname,expired)
                try:
                    with RouterOSClient(RouterOSCredential(url,'mm-monitor-synthetic','synthetic-only',str(ca_path) if trust else True)) as client:
                        if success:self.assertEqual(client.get('system/resource')[0]['version'],'7.24.2')
                        else:
                            with self.assertRaises(RouterOSError) as error:client.get('system/resource')
                            self.assertEqual(error.exception.code,'tls_verification_failed')
                finally:server.shutdown();server.server_close();thread.join(timeout=2)
