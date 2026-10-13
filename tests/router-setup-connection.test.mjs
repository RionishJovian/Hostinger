import test from 'node:test';
import assert from 'node:assert/strict';
import {routerSetupSteps} from '../src/router-setup.mjs';

test('router setup connect/check steps follow plan-backed connection fields', () => {
  const none = routerSetupSteps({sites: [{id: 's1'}], routers: [{id: 'r1', connection_state: 'unverified'}]});
  assert.equal(none.find(s => s.id === 'connect').done, false);
  assert.equal(none.find(s => s.id === 'check').done, false);

  const stale = routerSetupSteps({
    sites: [{id: 's1'}],
    routers: [{id: 'r1', connection_state: 'unverified', lifecycle_state: 'connected', management_read_verified_at: 1}],
  });
  assert.equal(stale.find(s => s.id === 'connect').done, true);
  assert.equal(stale.find(s => s.id === 'check').done, false);

  const fresh = routerSetupSteps({
    sites: [{id: 's1'}],
    routers: [{id: 'r1', connection_state: 'verified', connection_verified: true, lifecycle_state: 'connected'}],
  });
  assert.equal(fresh.find(s => s.id === 'connect').done, true);
  assert.equal(fresh.find(s => s.id === 'check').done, true);
});
