export const routerEverConnected = router =>
  router.connection_state === 'connected' ||
  router.connection_verified ||
  router.lifecycle_state === 'connected' ||
  Boolean(router.management_read_verified_at);

const routerFreshlyConnected = router =>
  router.connection_state === 'connected' || router.connection_verified;

/** Routers that still need Connect with Magic Hub (or secondary technician pairing). */
export function unconnectedRouters(routers = []) {
  return routers.filter(router => !(router.connection_state === 'connected' || router.connection_verified));
}

export function routerSetupSteps({sites = [], routers = []}) {
  const steps = [
    {id: 'shop', done: sites.length > 0, count: sites.length, page: 'Sites'},
    {id: 'register', done: routers.length > 0, count: routers.length, target: 'register-router'},
    {id: 'connect', done: routers.some(routerEverConnected), target: 'router-list'},
    {id: 'check', done: routers.some(routerFreshlyConnected), target: 'router-list'},
  ];
  const next = steps.findIndex(step => !step.done);
  return steps.map((step, index) => ({...step, state: step.done ? 'done' : index === next ? 'next' : 'later'}));
}

export const ATTENTION_PHASES = ['configuration_conflict', 'recovery_required', 'failed', 'rolling_back'];
export const changeNeedsAttention = changes => changes.some(change => ATTENTION_PHASES.includes(change.phase));
