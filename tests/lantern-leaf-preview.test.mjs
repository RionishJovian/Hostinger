import test from 'node:test';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {existsSync} from 'node:fs';
import {previewHotspotPages} from '../src/lantern-leaf-preview.mjs';

const settings = {
  business_name: 'Café <North>',
  welcome: 'Welcome <guest>',
  language: 'both',
  terms: 'Use fairly & safely',
  direct_purchase: true,
  payment_destination: 'KBZPay 09 <1>',
  payment_instructions: 'Send the amount.\nKeep the slip.',
  payment_methods: ['KBZPay', 'Cash']
};

test('owner preview renders the HotSpot pages, not a text summary', () => {
  const pages = previewHotspotPages(settings);
  assert.deepEqual(Object.keys(pages), ['login', 'connected', 'failed', 'status', 'signedOut']);
  for (const html of Object.values(pages)) {
    assert.match(html, /Café &lt;North&gt;/);
    assert.match(html, /class="seal"/);
    assert.match(html, /class="sheet"/);
    assert.match(html, /#0A1210/);
    assert.match(html, /Use fairly &amp; safely/);
    assert.doesNotMatch(html, /https?:\/\//);
    assert.doesNotMatch(html, /<script src=/);
  }
  assert.match(pages.login, /id="voucher"/);
  assert.match(pages.login, /ချိတ်ဆက်ရန်/);
  assert.match(pages.login, /Wi-Fi ကုဒ်/);
  assert.match(pages.login, /KBZPay 09 &lt;1&gt;/);
  assert.match(pages.login, /class="pay"/);
  assert.match(pages.login, /onsubmit="return false"/);
  assert.doesNotMatch(pages.login, /\$\(chap-id\)/);
  assert.match(pages.connected, /အင်တာနက် သုံးနိုင်ပါပြီ/);
  assert.match(pages.failed, /data-raw="invalid password"/);
  assert.match(pages.failed, /ကုဒ် မှားနေပါသည်/);
  assert.match(pages.status, /1h12m/);
  assert.match(pages.status, /800\.0MiB/);
  assert.match(pages.signedOut, /Session ပြီးဆုံးပါပြီ/);
});

test('owner preview matches the package the router will serve', () => {
  const python = existsSync('.venv/bin/python') ? '.venv/bin/python' : 'python3';
  const raw = execFileSync(python, ['-c', `
import io, json, zipfile
from backend.local_portal_package import build_local_hotspot_package
from backend.schemas import PortalConfig
cfg = PortalConfig(
    business_name='Café <North>', welcome='Welcome <guest>', language='both',
    terms='Use fairly & safely', direct_purchase=True,
    payment_destination='KBZPay 09 <1>', payment_instructions='Send the amount.\\nKeep the slip.',
    payment_methods=['KBZPay', 'Cash'])
package = build_local_hotspot_package(cfg, tenant_id='tenant_01', site_id=None, revision=1)
with zipfile.ZipFile(io.BytesIO(package)) as archive:
    print(archive.read('login.html').decode())
`], {encoding: 'utf8'});
  const login = previewHotspotPages(settings).login;
  for (const fragment of ['Café &lt;North&gt;', 'Welcome &lt;guest&gt;', 'class="seal"', 'class="sheet"', '#0A1210', 'ချိတ်ဆက်ရန်', 'Wi-Fi ကုဒ်', 'KBZPay 09 &lt;1&gt;', 'class="pay"', 'Use fairly &amp; safely', 'data-lang="my"']) {
    assert.match(login, new RegExp(fragment.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
    assert.match(raw, new RegExp(fragment.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  }
});

test('english-only and myanmar-only previews drop the language toggle', () => {
  const english = previewHotspotPages({...settings, language: 'en'}).login;
  assert.match(english, /Connect/);
  assert.doesNotMatch(english, /data-lang/);
  assert.doesNotMatch(english, /ချိတ်ဆက်ရန်/);
  const myanmar = previewHotspotPages({...settings, language: 'my', direct_purchase: false}).login;
  assert.match(myanmar, /ချိတ်ဆက်ရန်/);
  assert.doesNotMatch(myanmar, /data-lang/);
  assert.doesNotMatch(myanmar, /class="pay"/);
});

test('a script in the shop name stays text', () => {
  const login = previewHotspotPages({business_name: '<script>alert(1)</script>', welcome: 'https://evil.example/x', language: 'en'}).login;
  assert.match(login, /&lt;script&gt;alert\(1\)&lt;\/script&gt;/);
  assert.doesNotMatch(login, /<script>alert/);
  assert.doesNotMatch(login, /https?:\/\//);
});
