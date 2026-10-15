// @ts-nocheck
/**
 * Shared RouterOS snippets for clock honesty before TLS / schedules.
 * Product wall time is Asia/Yangon (UTC+06:30) — platform and routers stay locked
 * together so Hub linking, vouchers, and schedules stay aligned.
 */
import { APP_TIMEZONE } from "./time";

export const ROUTER_NTP_SERVERS = "pool.ntp.org,asia.pool.ntp.org";

/** Loose IANA-ish check for sites.timezone free-text (avoid injecting RouterOS junk). */
export function isPlausibleTimezone(tz: string | null | undefined): boolean {
  if (!tz) return false;
  const t = tz.trim();
  if (t.length < 3 || t.length > 64) return false;
  if (!/^[A-Za-z0-9_+\-/]+$/.test(t)) return false;
  if (!t.includes("/")) return false;
  return true;
}

/**
 * Router wall clock always uses the app timezone (Asia/Yangon).
 * Site timezone fields are informational only — do not diverge boards from the platform.
 */
export function resolveRouterTimezone(_siteTimezone?: string | null | undefined): string {
  return APP_TIMEZONE;
}

/**
 * RouterOS script fragment: enable NTP, set timezone, brief wait so cert
 * signing is less likely on a 1970 clock. Safe to paste more than once.
 */
export function routerosClockPrepSnippet(opts?: {
  timezone?: string;
  waitSeconds?: number;
}): string {
  const tz = resolveRouterTimezone(opts?.timezone);
  const wait = Math.max(2, Math.min(opts?.waitSeconds ?? 8, 30));
  return `:put "=== Clock prep (NTP + ${tz}) ==="
:do { /system/ntp/client/set enabled=yes } on-error={}
:if ([:len [/system/ntp/client/servers/find where address=pool.ntp.org]] = 0) do={ :do { /system/ntp/client/servers/add address=pool.ntp.org } on-error={} }
:if ([:len [/system/ntp/client/servers/find where address=asia.pool.ntp.org]] = 0) do={ :do { /system/ntp/client/servers/add address=asia.pool.ntp.org } on-error={} }
:do { /system clock set time-zone-autodetect=no time-zone-name=${tz} } on-error={}
:delay ${wait}s
:put ("Clock now: " . [/system clock get date] . " " . [/system clock get time] . " " . [/system clock get time-zone-name])
`;
}

// Live router clock alignment runs in the engine via Safe Change, not in the browser.
