export interface MemberIdentity {
  user_id: string;
}

export interface MetricDisplay {
  value: string;
  detail: string;
}

export interface ApiMetricInput {
  loading: boolean;
  errorStatus?: number;
  count: number;
  detail: string;
}

/** Count active user identities once, even when they belong to several tenants. */
export function countUniqueMembers(members: readonly MemberIdentity[]): number {
  const userIds = new Set<string>();

  for (const member of members) {
    const userId = member.user_id.trim();
    if (userId.length > 0) userIds.add(userId);
  }

  return userIds.size;
}

/** Render API metrics without falling back to fictitious demo values. */
export function formatApiMetric(input: ApiMetricInput): MetricDisplay {
  if (input.loading) {
    return { value: "—", detail: "Chargement depuis l'API…" };
  }

  if (input.errorStatus === 401) {
    return { value: "—", detail: "Session expirée — reconnectez-vous" };
  }

  if (input.errorStatus === 403) {
    return { value: "—", detail: "Accès restreint — permission requise" };
  }

  if (input.errorStatus !== undefined) {
    return { value: "—", detail: "API indisponible — aucune valeur simulée affichée" };
  }

  const count = Number.isFinite(input.count)
    ? Math.max(0, Math.floor(input.count))
    : 0;

  return {
    value: String(count).padStart(2, "0"),
    detail: input.detail,
  };
}
