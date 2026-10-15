import test from "node:test";
import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { filterNavigation } from "../owner-web/src/lib/navigation.mjs";

const items = [
  { to: "/app/home", label: "Home" },
  { to: "/app/agent", label: "Agent", agentOnly: true },
  { to: "/app/tenants", label: "Tenants", platformOnly: true },
  { to: "/app/test-lab", label: "Test lab", platformOnly: true },
];

test("platform-only navigation is shown only to the platform owner", () => {
  assert.deepEqual(filterNavigation(items, { role: "platform", platform_owner: true }).map((item) => item.label), ["Tenants", "Test lab"]);
  assert.deepEqual(filterNavigation(items, { role: "platform", platform_owner: false }), []);
  assert.deepEqual(filterNavigation(items, { role: "sme", platform_owner: true }).map((item) => item.label), ["Home"]);
});

test("agent navigation is shown only to agent accounts", () => {
  assert.deepEqual(filterNavigation(items, { role: "agent" }).map((item) => item.label), ["Agent"]);
  assert.equal(filterNavigation(items, { role: "sme" }).some((item) => item.label === "Agent"), false);
  assert.equal(filterNavigation(items, { role: "platform", platform_owner: true }).some((item) => item.label === "Agent"), false);
});

async function sourceFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const nested = await Promise.all(entries.map((entry) => entry.isDirectory() ? sourceFiles(join(directory, entry.name)) : [join(directory, entry.name)]));
  return nested.flat();
}

test("owner web contains no Supabase imports or calls", async () => {
  const files = await sourceFiles(fileURLToPath(new URL("../owner-web/src", import.meta.url)));
  for (const file of files) assert.doesNotMatch(await readFile(file, "utf8"), /supabase|createServerFn|useServerFn/i, file);
});

test("copied Lovable screens under src/legacy exist and carry no Supabase code", async () => {
  const files = await sourceFiles(fileURLToPath(new URL("../owner-web/src/legacy", import.meta.url)));
  assert.ok(files.length > 100, "legacy screen copy is present");
  assert.equal(files.some((file) => file.endsWith(".source")), false);
  for (const file of files) assert.doesNotMatch(await readFile(file, "utf8"), /supabase|createServerFn|useServerFn/i, file);
});

test("kept screens are routed to the real Lovable copies with role gates", async () => {
  const router = await readFile(fileURLToPath(new URL("../owner-web/src/router.tsx", import.meta.url)), "utf8");
  assert.doesNotMatch(router, /RestoredScreenPage|TestLabPage/);
  assert.match(router, /dataRoute\("tenants", legacyScreen\(L_users, "platform"\)\)/);
  assert.match(router, /legacyScreen\(L_test_lab, "platform"\)/);
  assert.match(router, /legacyScreen\(L_agent, "agent"\)/);
  assert.match(router, /legacyScreen\(L_terminal, "owner"\)/);
});

test("quick setup keeps the old Lovable API user and WireGuard peer cleanup step", async () => {
  const steps = await readFile(fileURLToPath(new URL("../owner-web/src/legacy/QuickSetupSteps.tsx", import.meta.url)), "utf8");
  assert.match(steps, /Remove the old Lovable API user and its old WireGuard peer/);
  assert.match(steps, /\/v1\/owner\/scripts\/run/);
});
