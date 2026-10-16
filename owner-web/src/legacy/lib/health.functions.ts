// Engine data layer for the copied Lovable screen: calls go to /v1/owner/* or report coming soon.
import { engineFn } from "@/engine";
export const listHealthHistory = engineFn("listHealthHistory");
export const runHealthSweep = engineFn("runHealthSweep");
export const listIncidents = engineFn("listIncidents");
export const acknowledgeIncident = engineFn("acknowledgeIncident");
export const dismissIncident = engineFn("dismissIncident");
export const listAlertRules = engineFn("listAlertRules");
export const saveAlertRule = engineFn("saveAlertRule");
export const getNotificationPrefs = engineFn("getNotificationPrefs");
export const saveNotificationPrefs = engineFn("saveNotificationPrefs");
