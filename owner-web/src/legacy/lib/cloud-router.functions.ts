// @ts-nocheck
// Engine data layer for the copied Lovable screen: calls go to /v1/owner/* or report coming soon.
import { engineFn } from "@/engine";
export const MAGIC_HUB_REQUIRED_READ_PATHS = [
  "/interface/bridge",
  "/interface/bridge/port",
  "/ip/route",
  "/ip/dhcp-server",
  "/ip/firewall/nat",
  "/ip/firewall/filter",
] as const;
export type Json = any;
export type CloudStatus = any;
export type CloudRouterState = any;
export type CloudProvisionResult = any;
export const cloudRouterState = engineFn("cloudRouterState");
export const provisionCloudRouter = engineFn("provisionCloudRouter");
export const checkCloudRouter = engineFn("checkCloudRouter");
export const disableCloudRouter = engineFn("disableCloudRouter");
export const cloudRouterOperation = engineFn("cloudRouterOperation");
export const cloudRouterRaw = engineFn("cloudRouterRaw");
export const verifyMagicHubRequiredReads = engineFn("verifyMagicHubRequiredReads");
export const runProvisionHubPeer = engineFn("runProvisionHubPeer");
export const runTeardownHubPeer = engineFn("runTeardownHubPeer");
