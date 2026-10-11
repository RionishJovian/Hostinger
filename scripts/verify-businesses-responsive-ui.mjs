import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { mkdir, readFile, rm, writeFile } from 'node:fs/promises';

const dir = '.ui-check';
await mkdir(dir, { recursive: true });
try {
  const bundle = await build({
    entryPoints: ['src/BusinessOnboarding.jsx'],
    bundle: true,
    platform: 'node',
    format: 'esm',
    external: ['react'],
    write: false,
  });
  await writeFile(`${dir}/businesses-responsive.mjs`, bundle.outputFiles[0].text);
  const { default: BusinessOnboarding } = await import(`../${dir}/businesses-responsive.mjs`);
  const React = await import('react');
  const { renderToStaticMarkup } = await import('react-dom/server');
  const html = renderToStaticMarkup(React.createElement(BusinessOnboarding, {
    businesses: [{ id: 'tenant-acceptance-123', name: 'Sample cafe with a long name', owners: [{ id: 'owner-1', username: 'owner@example.test', active: true, must_change_password: false }] }],
    resets: [{ id: 'reset-1', created: 1791417600, username: 'owner@example.test', tenant_id: 'tenant-acceptance-123', actor_id: 'operator-1', reason: 'Verified test recovery' }],
    act: async () => null,
    busy: false,
  }));
  assert.match(html, /desktop-only/);
  assert.match(html, /<table>/);
  assert.match(html, /business-cards mobile-only/);
  assert.match(html, /Registered businesses and owners/);
  assert.match(html, /Business ID/);
  assert.match(html, /tenant-acceptance-123/);
  assert.match(html, /owner@example\.test/);
  assert.match(html, /Account status/);
  assert.match(html, /Reset owner password/);
  assert.match(html, /Owner password reset history/);
  assert.match(html, /Tenant ID/);
  assert.match(html, /Verified test recovery/);

  const css = await readFile('src/styles.css', 'utf8');
  assert.match(css, /@media\s*\(max-width:\s*720px\)[^{]*\{[^}]*\.desktop-only\{display:none!important\}/);
  assert.match(css, /\.business-card \.button\{min-height:44px;width:100%/);
  assert.match(css, /overflow-wrap:anywhere/);
  assert.match(css, /\.tablewrap\{overflow-x:auto\}/);
  assert.match(css, /\.formgrid,\.details\{grid-template-columns:1fr\}/);
  const workspace = await readFile('src/AccountWorkspace.jsx', 'utf8');
  assert.match(workspace, /onClick=\{logout\}><SignOut size=\{18\}\/><span>\{demo\?t\('shell','exitDemo'\):localizeSme\?t\('shell','signOut'\):'Sign out'\}<\/span><\/button>/);
  assert.match(workspace, /forced onChangePassword=\{changePassword\} onLogout=\{logout\}/);
  assert.match(workspace, /await revokeCurrentSession\(api\);throw Error\('Use a guest account/);
  assert.doesNotMatch(workspace, /api\.request\(['"]auth\/logout['"]/);
  assert.match(workspace, /await revokeCurrentSession\(api\);setUser\(null\);setS\(empty\);setNotice\('Signed out\.'\)/);
  await mkdir('dist/client', { recursive: true });
  await writeFile('dist/client/businesses-responsive-preview.html', `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Businesses responsive acceptance preview</title><style>${css}\nbody{padding:24px}.preview{max-width:1050px;margin:auto}.preview-note{margin-bottom:18px;color:#555;font:14px/1.5 Arial}</style></head><body><main class="preview"><p class="preview-note">Static local-only sample data. No API, account, or server is connected.</p>${html}</main></body></html>`);
  console.log('Businesses UI regression checks passed: desktop table retained; labeled mobile cards preserve tenant, owner, status, reset and audit-history details with 44px actions.');
} finally {
  await rm(`${dir}/businesses-responsive.mjs`, { force: true });
}
