// @ts-nocheck
// Engine data layer for the copied Lovable screen: calls go to /v1/owner/* or report coming soon.
import { engineFn } from "@/engine";
export const telegramSetupStatus = engineFn("telegramSetupStatus");
export const registerTelegramWebhook = engineFn("registerTelegramWebhook");
export const sendTelegramTest = engineFn("sendTelegramTest");
export const listNotifierAudit = engineFn("listNotifierAudit");
