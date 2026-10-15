export function filterNavigation(items, account) {
  return items.filter((item) => {
    if (item.platformOnly) return account?.role === "platform" && account.platform_owner === true;
    if (item.agentOnly) return account?.role === "agent";
    if (account?.role !== "sme") return false;
    if (item.ownerOnly) return !account.staff_profile;
    return true;
  });
}
