export type NavigationRule = { ownerOnly?: boolean; agentOnly?: boolean; platformOnly?: boolean };
export type NavigationAccount = { role: string; platform_owner?: boolean; staff_profile?: string | null };
export function filterNavigation<T extends NavigationRule>(items: T[], account: NavigationAccount | null | undefined): T[];
