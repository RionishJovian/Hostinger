const routerEverConnected = router =>
  router.lifecycle_state === 'connected' ||
  Boolean(router.management_read_verified_at) ||
  router.connection_verified ||
  router.connection_state === 'verified';

const routerFreshlyConnected = router =>
  router.connection_verified || router.connection_state === 'verified';

export function routerSetupSteps({sites = [], routers = []}) {
  const steps = [
    {id: 'shop', done: sites.length > 0, count: sites.length, page: 'Sites'},
    {id: 'register', done: routers.length > 0, count: routers.length, target: 'register-router'},
    {id: 'connect', done: routers.some(routerEverConnected), page: 'Get help'},
    {id: 'check', done: routers.some(routerFreshlyConnected)},
  ];
  const next = steps.findIndex(step => !step.done);
  return steps.map((step, index) => ({...step, state: step.done ? 'done' : index === next ? 'next' : 'later'}));
}

export const ATTENTION_PHASES = ['configuration_conflict', 'recovery_required', 'failed', 'rolling_back'];
export const changeNeedsAttention = changes => changes.some(change => ATTENTION_PHASES.includes(change.phase));
