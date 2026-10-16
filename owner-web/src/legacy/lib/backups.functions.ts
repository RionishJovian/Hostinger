// @ts-nocheck
// Engine data layer for the copied Lovable screen: calls go to /v1/owner/* or report coming soon.
import { engineFn } from "@/engine";
export const listDbBackups = engineFn("listDbBackups");
export const signDbBackup = engineFn("signDbBackup");
export const runDbBackupNow = engineFn("runDbBackupNow");
