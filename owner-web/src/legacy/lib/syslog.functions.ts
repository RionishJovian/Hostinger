// @ts-nocheck
// Engine data layer for the copied Lovable screen: calls go to /v1/owner/* or report coming soon.
import { engineFn } from "@/engine";
export type PairedLogSource = any;
export type PairedLogSyncResult = any;
export const listSyslogEvents = engineFn("listSyslogEvents");
export const listSyslogTokens = engineFn("listSyslogTokens");
export const createSyslogToken = engineFn("createSyslogToken");
export const deleteSyslogToken = engineFn("deleteSyslogToken");
export const translateSyslogEvents = engineFn("translateSyslogEvents");
export const deleteSyslogEvent = engineFn("deleteSyslogEvent");
export const listPairedLogSources = engineFn("listPairedLogSources");
export const syncPairedRouterLogs = engineFn("syncPairedRouterLogs");
