export interface MemberIdentity {
  user_id: string;
}

export interface AuditEventTimestamp {
  id: string;
  occurred_at: string;
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

/** Return the newest persisted audit events without mutating query-cache arrays. */
export function latestAuditEvents<T extends AuditEventTimestamp>(
  events: readonly T[],
  limit = 3,
): T[] {
  const boundedLimit = Number.isFinite(limit)
    ? Math.min(100, Math.max(0, Math.trunc(limit)))
    : 3;

  return [...events]
    .sort((left, right) => {
      const leftTime = Date.parse(left.occurred_at);
      const rightTime = Date.parse(right.occurred_at);
      const safeLeftTime = Number.isFinite(leftTime)
        ? leftTime
        : Number.NEGATIVE_INFINITY;
      const safeRightTime = Number.isFinite(rightTime)
        ? rightTime
        : Number.NEGATIVE_INFINITY;
      const timeDifference = safeRightTime - safeLeftTime;

      if (Number.isFinite(timeDifference) && timeDifference !== 0) {
        return timeDifference;
      }

      return left.id.localeCompare(right.id);
    })
    .slice(0, boundedLimit);
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
