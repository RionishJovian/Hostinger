// @ts-nocheck
// Engine data layer for the copied Lovable screen: calls go to /v1/owner/* or report coming soon.
import { engineFn } from "@/engine";
export type ConnectorSummary = any;
export type DiscoveredRouter = any;
export const listConnectors = engineFn("listConnectors");
export const listConnectorDevices = engineFn("listConnectorDevices");
export const listDiscoveredRouters = engineFn("listDiscoveredRouters");
export const saveConnector = engineFn("saveConnector");
export const setConnectorEnabled = engineFn("setConnectorEnabled");
export const generatePairingCode = engineFn("generatePairingCode");
export const unpairConnector = engineFn("unpairConnector");
export const deleteConnector = engineFn("deleteConnector");
export const testConnector = engineFn("testConnector");
