import test from 'node:test';
import assert from 'node:assert/strict';
import QRCode from 'qrcode';
import {isSecurePairingContext,technicianPairingUrl} from '../src/magic-connect-url.mjs';

test('pairing QR points to the technician page and keeps the one-time code in the fragment',()=>{
 const location={origin:'https://acceptance.example',pathname:'/app',protocol:'https:',hostname:'acceptance.example'};
 const url=new URL(technicianPairingUrl(location,'ABCD-EFGH-1234'));
 assert.equal(url.searchParams.get('magic_connect'),'technician');
 assert.equal(url.hash,'#pair=ABCD-EFGH-1234');
 assert.equal(url.search.includes('ABCD'),false);
});

test('pairing QR rejects non-TLS remote origins but permits loopback development',()=>{
 assert.equal(isSecurePairingContext({protocol:'http:',hostname:'192.0.2.5'}),false);
 assert.throws(()=>technicianPairingUrl({origin:'http://192.0.2.5',pathname:'/',protocol:'http:',hostname:'192.0.2.5'},'PAIR'),/HTTPS or localhost/);
 assert.equal(isSecurePairingContext({protocol:'http:',hostname:'localhost'}),true);
});

test('QR encoder produces an image for the opaque pairing deep link',async()=>{
 const location={origin:'https://acceptance.example',pathname:'/',protocol:'https:',hostname:'acceptance.example'};
 const data=await QRCode.toDataURL(technicianPairingUrl(location,'ABCD-EFGH-1234'),{errorCorrectionLevel:'M'});
 assert.match(data,/^data:image\/png;base64,/);
});
