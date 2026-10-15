// @ts-nocheck
// Screens call engine functions directly in the browser; no server functions.
export function useEngineFn<T>(fn: T): T { return fn; }
export function createClientOnlyFn<T extends (...args: any[]) => any>(fn: T): T { return fn; }
