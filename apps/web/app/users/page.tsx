"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { ShieldCheck, Users } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { PageHeading } from "@/components/page-heading";
import {
  ApiError,
  getCurrentUser,
  getOrganizationRoles,
  getOrganizations,
} from "@/lib/api";
import {
  MembershipApiError,
  deleteOrganizationMembership,
  getOrganizationMembers,
  updateOrganizationMembership,
} from "@/lib/membership-api";

function errorStatus(error: unknown): number | undefined {
  if (error instanceof ApiError || error instanceof MembershipApiError) {
    return error.status;
  }
  return undefined;
}

function AccessError({ error }: { error: unknown }) {
  const status = errorStatus(error);
  if (status === 401) {
    return <p role="alert" className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">Session requise. <Link className="font-semibold underline" href="/login">Se connecter</Link>.</p>;
  }
  if (status === 403) {
    return <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">Accès refusé : votre membership ne possède pas la permission demandée.</p>;
  }
  if (status === 404) {
    return <p role="alert" className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">Organisation introuvable ou non accessible avec cette session.</p>;
  }
  return <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">Erreur lors de la lecture de l’API. Vérifiez le Control Plane puis réessayez.</p>;
}

function MutationError({ error }: { error: unknown }) {
  if (error instanceof MembershipApiError && error.status === 401) {
    return <p role="alert" className="text-sm text-rose-700">Session expirée. Reconnectez-vous avant de modifier les memberships.</p>;
  }
  if (error instanceof MembershipApiError && error.status === 403) {
    return <p role="alert" className="text-sm text-rose-700">Action refusée : vérifiez la permission members.manage, l’origine et le jeton CSRF.</p>;
  }
  if (error instanceof MembershipApiError && error.status === 404) {
    return <p role="alert" className="text-sm text-rose-700">Membership ou rôle introuvable dans cette organisation.</p>;
  }
  if (error instanceof MembershipApiError && error.status === 409) {
    return <p role="alert" className="text-sm text-rose-700">{error.message}</p>;
  }
  return <p role="alert" className="text-sm text-rose-700">La mutation a échoué. Vérifiez l’API puis réessayez.</p>;
}

export default function UsersPage() {
  const queryClient = useQueryClient();
  const [selectedOrganizationId, setSelectedOrganizationId] = useState("");
  const [csrfToken, setCsrfToken] = useState<string | null>(null);
  const [roleSelections, setRoleSelections] = useState<Record<string, string>>({});
  const [actionMessage, setActionMessage] = useState("");

  useEffect(() => {
    const requestedOrganization = new URLSearchParams(window.location.search).get("organization");
    if (requestedOrganization) setSelectedOrganizationId(requestedOrganization);
    setCsrfToken(window.sessionStorage.getItem("eii_csrf_token"));
  }, []);

  const organizations = useQuery({
    queryKey: ["organizations"],
    queryFn: getOrganizations,
    retry: false,
  });
  const organizationId =
    selectedOrganizationId || organizations.data?.[0]?.id || "";

  const currentUser = useQuery({
    queryKey: ["current-user"],
    queryFn: getCurrentUser,
    enabled: Boolean(csrfToken),
    retry: false,
    staleTime: 30_000,
  });
  const members = useQuery({
    queryKey: ["organization-members", organizationId],
    queryFn: () => getOrganizationMembers(organizationId),
    enabled: Boolean(organizationId),
    retry: false,
  });
  const roles = useQuery({
    queryKey: ["organization-roles", organizationId],
    queryFn: () => getOrganizationRoles(organizationId),
    enabled: Boolean(organizationId),
    retry: false,
  });

  useEffect(() => {
    if (members.data) {
      setRoleSelections(
        Object.fromEntries(
          members.data.map((member) => [member.membership_id, member.role_id]),
        ),
      );
    }
  }, [members.data]);

  const updateMembership = useMutation({
    mutationFn: ({
      membershipId,
      roleId,
    }: {
      membershipId: string;
      roleId: string;
    }) => {
      if (!csrfToken) {
        throw new MembershipApiError(403, "Missing session CSRF token");
      }
      return updateOrganizationMembership(
        organizationId,
        membershipId,
        roleId,
        csrfToken,
      );
    },
    onMutate: () => setActionMessage(""),
    onSuccess: async () => {
      setActionMessage("Rôle mis à jour et événement d’audit enregistré.");
      await queryClient.invalidateQueries({
        queryKey: ["organization-members", organizationId],
      });
    },
  });

  const removeMembership = useMutation({
    mutationFn: (membershipId: string) => {
      if (!csrfToken) {
        throw new MembershipApiError(403, "Missing session CSRF token");
      }
      return deleteOrganizationMembership(
        organizationId,
        membershipId,
        csrfToken,
      );
    },
    onMutate: () => setActionMessage(""),
    onSuccess: async () => {
      setActionMessage("Membership retiré et événement d’audit enregistré.");
      await queryClient.invalidateQueries({
        queryKey: ["organization-members", organizationId],
      });
    },
  });

  const mutationError = updateMembership.error ?? removeMembership.error;

  return (
    <AppShell>
      <PageHeading
        eyebrow="Administration"
        title="Utilisateurs & rôles"
        description="Membres actifs et rôles de l'organisation sélectionnée, lus depuis les endpoints protégés par le RBAC serveur."
      />

      {organizations.isLoading && <p aria-busy="true" className="rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-500">Chargement des organisations…</p>}
      {organizations.isError && <AccessError error={organizations.error} />}

      {organizations.data && (
        <>
          {organizations.data.length === 0 ? (
            <p className="rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-500">Aucune organisation accessible. Les membres ne sont pas simulés sur cette page.</p>
          ) : (
            <>
              <label className="mb-5 block max-w-xl text-sm font-medium text-slate-700">
                Organisation
                <select
                  value={organizationId}
                  onChange={(event) => {
                    setSelectedOrganizationId(event.target.value);
                    setActionMessage("");
                    updateMembership.reset();
                    removeMembership.reset();
                  }}
                  className="mt-2 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm"
                >
                  {organizations.data.map((organization) => (
                    <option key={organization.id} value={organization.id}>{organization.name}</option>
                  ))}
                </select>
              </label>

              <section className="mb-5 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
                  <div>
                    <h2 className="font-semibold text-slate-900">Membres actifs</h2>
                    <p className="mt-1 text-xs text-slate-500">GET /organizations/{'{id}'}/members · permission members.read</p>
                  </div>
                  <span className="rounded-lg bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-700">API réelle</span>
                </div>

                <div className="border-b border-slate-100 bg-slate-50 px-5 py-3 text-xs leading-5 text-slate-600">
                  Les actions nécessitent une session active et la permission <code>members.manage</code>. Le serveur vérifie également l’origine et le jeton CSRF. La suppression du dernier propriétaire actif est refusée.
                </div>
                {members.isLoading && <p aria-busy="true" className="p-5 text-sm text-slate-500">Chargement des membres…</p>}
                {members.isError && <div className="p-5"><AccessError error={members.error} /></div>}
                {members.data && (members.data.length === 0
                  ? <p className="p-5 text-sm text-slate-500">Aucun membre actif retourné par l’API.</p>
                  : <div className="overflow-x-auto"><table className="w-full min-w-[820px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3">Utilisateur</th><th className="px-5 py-3">Rôle actuel</th><th className="px-5 py-3">Membre depuis</th><th className="px-5 py-3">Actions</th></tr></thead><tbody className="divide-y divide-slate-100">{members.data.map((member) => {
                    const selectedRoleId = roleSelections[member.membership_id] ?? member.role_id;
                    const roleChanged = selectedRoleId !== member.role_id;
                    const isSelf = currentUser.data?.id === member.user_id;
                    return (
                      <tr key={member.membership_id}>
                        <td className="px-5 py-4"><p className="font-medium text-slate-900">{member.display_name}</p><p className="text-xs text-slate-500">{member.email}</p></td>
                        <td className="px-5 py-4"><span className="inline-flex items-center gap-2 rounded-full bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700"><Users aria-hidden="true" className="h-3.5 w-3.5" />{member.role}</span></td>
                        <td className="px-5 py-4 text-xs text-slate-500">{new Date(member.joined_at).toLocaleDateString("fr-FR")}</td>
                        <td className="px-5 py-4">
                          <div className="flex flex-wrap items-center gap-2">
                            <select
                              aria-label={`Nouveau rôle pour ${member.display_name}`}
                              value={selectedRoleId}
                              onChange={(event) => setRoleSelections((current) => ({ ...current, [member.membership_id]: event.target.value }))}
                              disabled={!csrfToken || !currentUser.data || !roles.data || updateMembership.isPending || removeMembership.isPending}
                              className="rounded-lg border border-slate-300 bg-white px-2 py-2 text-xs disabled:bg-slate-100"
                            >
                              {(roles.data ?? []).map((role) => <option key={role.id} value={role.id}>{role.name}</option>)}
                            </select>
                            <button
                              type="button"
                              onClick={() => updateMembership.mutate({ membershipId: member.membership_id, roleId: selectedRoleId })}
                              disabled={!csrfToken || !currentUser.data || !roleChanged || updateMembership.isPending || removeMembership.isPending}
                              className="rounded-lg bg-accent px-3 py-2 text-xs font-semibold text-white hover:bg-accent-dark disabled:cursor-not-allowed disabled:opacity-40"
                            >
                              {updateMembership.isPending ? "Enregistrement…" : "Enregistrer"}
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                if (window.confirm(`Retirer ${member.display_name} de cette organisation ?`)) {
                                  removeMembership.mutate(member.membership_id);
                                }
                              }}
                              disabled={!csrfToken || !currentUser.data || isSelf || removeMembership.isPending || updateMembership.isPending}
                              title={isSelf ? "Un membre ne peut pas retirer son propre membership" : "Retirer ce membership"}
                              className="rounded-lg border border-rose-200 px-3 py-2 text-xs font-semibold text-rose-700 hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-40"
                            >
                              {removeMembership.isPending ? "Suppression…" : "Retirer"}
                            </button>
                          </div>
                          {isSelf && <p className="mt-1 text-[11px] text-slate-400">Votre propre membership ne peut pas être retiré ici.</p>}
                        </td>
                      </tr>
                    );
                  })}</tbody></table></div>
                )}
                {!csrfToken && <p className="border-t border-slate-100 px-5 py-3 text-xs text-amber-800">Session non initialisée dans ce navigateur. <Link className="font-semibold underline" href="/login">Reconnectez-vous</Link> pour activer les mutations.</p>}
                {mutationError && <div className="border-t border-slate-100 px-5 py-3"><MutationError error={mutationError} /></div>}
                {actionMessage && <p role="status" className="border-t border-slate-100 px-5 py-3 text-sm text-emerald-700">{actionMessage}</p>}
              </section>

              <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
                  <div>
                    <h2 className="font-semibold text-slate-900">Rôles et permissions</h2>
                    <p className="mt-1 text-xs text-slate-500">GET /organizations/{'{id}'}/roles · permission roles.read</p>
                  </div>
                  <ShieldCheck aria-hidden="true" className="h-5 w-5 text-accent" />
                </div>
                {roles.isLoading && <p aria-busy="true" className="p-5 text-sm text-slate-500">Chargement des rôles…</p>}
                {roles.isError && <div className="p-5"><AccessError error={roles.error} /></div>}
                {roles.data && <ul className="divide-y divide-slate-100">{roles.data.map((role) => <li key={role.id} className="px-5 py-4"><div className="flex flex-wrap items-center gap-2"><p className="font-medium text-slate-900">{role.name}</p>{role.is_system && <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold uppercase text-slate-600">Système</span>}</div>{role.description && <p className="mt-1 text-xs text-slate-500">{role.description}</p>}<p className="mt-2 text-xs leading-5 text-slate-600">{role.permissions.length ? role.permissions.join(" · ") : "Aucune permission attribuée"}</p></li>)}</ul>}
              </section>

              <p className="mt-4 text-xs text-slate-400">Les memberships existants peuvent être modifiés ou retirés via l’API réelle. Les invitations, la création de comptes et l’administration du catalogue de rôles ne sont pas implémentées.</p>
            </>
          )}
        </>
      )}
    </AppShell>
  );
}
