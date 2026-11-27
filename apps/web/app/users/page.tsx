"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { Copy, ShieldCheck, Users } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { PageHeading } from "@/components/page-heading";
import {
  ApiError,
  getCurrentUser,
  getOrganizationRoles,
  getOrganizations,
} from "@/lib/api";
import { useCsrfToken } from "@/lib/csrf-token";
import {
  InvitationApiError,
  createOrganizationInvitation,
  listOrganizationInvitations,
  revokeOrganizationInvitation,
  type OrganizationInvitation,
  type OrganizationInvitationCreateResponse,
} from "@/lib/invitation-api";
import {
  MembershipApiError,
  createOrganizationMembership,
  deleteOrganizationMembership,
  getOrganizationMembers,
  updateMemberStatus,
  updateOrganizationMembership,
} from "@/lib/membership-api";

function errorStatus(error: unknown): number | undefined {
  if (
    error instanceof ApiError ||
    error instanceof MembershipApiError ||
    error instanceof InvitationApiError
  ) {
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
  if (error instanceof InvitationApiError && error.status === 403) {
    return <p role="alert" className="text-sm text-rose-700">Action refusée : vérifiez la permission members.manage, l’origine et le jeton CSRF.</p>;
  }
  if (error instanceof InvitationApiError && error.status === 404) {
    return <p role="alert" className="text-sm text-rose-700">Invitation ou rôle introuvable dans cette organisation.</p>;
  }
  if (errorStatus(error) === 409 && error instanceof Error) {
    return <p role="alert" className="text-sm text-rose-700">{error.message}</p>;
  }
  return <p role="alert" className="text-sm text-rose-700">La mutation a échoué. Vérifiez l’API puis réessayez.</p>;
}

function UsersPageContent() {
  const queryClient = useQueryClient();
  const searchParams = useSearchParams();
  const requestedOrganizationId = searchParams.get("organization") ?? "";
  const [manualSelection, setManualSelection] = useState<{ query: string; id: string } | null>(null);
  const csrfToken = useCsrfToken();
  const [roleOverrides, setRoleOverrides] = useState<Record<string, string>>({});
  const [actionMessage, setActionMessage] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);
  const [newMemberUserId, setNewMemberUserId] = useState("");
  const [newMemberRoleId, setNewMemberRoleId] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRoleId, setInviteRoleId] = useState("");
  const [inviteExpiryDays, setInviteExpiryDays] = useState(7);
  const [createdInvitation, setCreatedInvitation] =
    useState<OrganizationInvitationCreateResponse | null>(null);
  const [copiedLink, setCopiedLink] = useState(false);

  const organizations = useQuery({
    queryKey: ["organizations"],
    queryFn: getOrganizations,
    retry: false,
  });
  const organizationId =
    (manualSelection?.query === requestedOrganizationId ? manualSelection.id : "") ||
    requestedOrganizationId ||
    organizations.data?.[0]?.id ||
    "";

  const currentUser = useQuery({
    queryKey: ["current-user"],
    queryFn: getCurrentUser,
    enabled: Boolean(csrfToken),
    retry: false,
    staleTime: 30_000,
  });
  const members = useQuery({
    queryKey: ["organization-members", organizationId, includeInactive],
    queryFn: () => getOrganizationMembers(organizationId, includeInactive),
    enabled: Boolean(organizationId),
    retry: false,
  });
  const roles = useQuery({
    queryKey: ["organization-roles", organizationId],
    queryFn: () => getOrganizationRoles(organizationId),
    enabled: Boolean(organizationId),
    retry: false,
  });
  const invitations = useQuery({
    queryKey: ["organization-invitations", organizationId],
    queryFn: () => listOrganizationInvitations(organizationId),
    enabled: Boolean(organizationId),
    retry: false,
  });


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
      setRoleOverrides({});
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
      setRoleOverrides({});
      await queryClient.invalidateQueries({
        queryKey: ["organization-members", organizationId],
      });
    },
  });

  const toggleStatus = useMutation({
    mutationFn: ({
      membershipId,
      isActive,
    }: {
      membershipId: string;
      isActive: boolean;
    }) => {
      if (!csrfToken) {
        throw new MembershipApiError(403, "Missing session CSRF token");
      }
      return updateMemberStatus(
        organizationId,
        membershipId,
        isActive,
        csrfToken,
      );
    },
    onMutate: () => setActionMessage(""),
    onSuccess: async (member) => {
      setActionMessage(
        member.is_active
          ? "Membre réactivé et événement d’audit enregistré."
          : "Membre désactivé et événement d’audit enregistré.",
      );
      await queryClient.invalidateQueries({
        queryKey: ["organization-members", organizationId],
      });
    },
  });

  const addMembership = useMutation({
    mutationFn: ({ userId, roleId }: { userId: string; roleId: string }) => {
      if (!csrfToken) {
        throw new MembershipApiError(403, "Missing session CSRF token");
      }
      return createOrganizationMembership(
        organizationId,
        userId,
        roleId,
        csrfToken,
      );
    },
    onMutate: () => setActionMessage(""),
    onSuccess: async () => {
      setActionMessage("Membre ajouté et événement d’audit enregistré.");
      setNewMemberUserId("");
      setNewMemberRoleId("");
      await queryClient.invalidateQueries({
        queryKey: ["organization-members", organizationId],
      });
    },
  });

  const createInvitation = useMutation({
    mutationFn: ({
      email,
      roleId,
      expiresInDays,
    }: {
      email: string;
      roleId: string;
      expiresInDays: number;
    }) => {
      if (!csrfToken) {
        throw new InvitationApiError(403, "Missing session CSRF token");
      }
      return createOrganizationInvitation(
        organizationId,
        email,
        roleId,
        expiresInDays,
        csrfToken,
      );
    },
    onMutate: () => {
      setActionMessage("");
      setCreatedInvitation(null);
      setCopiedLink(false);
    },
    onSuccess: async (invitation) => {
      setCreatedInvitation(invitation);
      setInviteEmail("");
      await queryClient.invalidateQueries({
        queryKey: ["organization-invitations", organizationId],
      });
    },
  });

  const revokeInvitation = useMutation({
    mutationFn: (invitationId: string) => {
      if (!csrfToken) {
        throw new InvitationApiError(403, "Missing session CSRF token");
      }
      return revokeOrganizationInvitation(
        organizationId,
        invitationId,
        csrfToken,
      );
    },
    onMutate: () => setActionMessage(""),
    onSuccess: async () => {
      setActionMessage("Invitation révoquée et événement d’audit enregistré.");
      await queryClient.invalidateQueries({
        queryKey: ["organization-invitations", organizationId],
      });
    },
  });

  const mutationError =
    updateMembership.error ??
    removeMembership.error ??
    toggleStatus.error ??
    addMembership.error ??
    createInvitation.error ??
    revokeInvitation.error;

  const mutationPending =
    updateMembership.isPending ||
    removeMembership.isPending ||
    toggleStatus.isPending ||
    addMembership.isPending ||
    createInvitation.isPending ||
    revokeInvitation.isPending;

  function invitationStatusLabel(invitation: OrganizationInvitation): string {
    switch (invitation.status) {
      case "pending":
        return "En attente";
      case "accepted":
        return "Acceptée";
      case "revoked":
        return "Révoquée";
      case "expired":
        return "Expirée";
    }
  }

  async function copyInvitationLink() {
    if (!createdInvitation) {
      return;
    }
    const link = `${window.location.origin}${createdInvitation.accept_path}`;
    try {
      await navigator.clipboard.writeText(link);
      setCopiedLink(true);
    } catch {
      setCopiedLink(false);
    }
  }

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
                    setManualSelection({ query: requestedOrganizationId, id: event.target.value });
                    setRoleOverrides({});
                    setActionMessage("");
                    setCreatedInvitation(null);
                    updateMembership.reset();
                    removeMembership.reset();
                    toggleStatus.reset();
                    addMembership.reset();
                    createInvitation.reset();
                    revokeInvitation.reset();
                  }}
                  className="mt-2 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm"
                >
                  {organizations.data.map((organization) => (
                    <option key={organization.id} value={organization.id}>{organization.name}</option>
                  ))}
                </select>
              </label>

              <section className="mb-5 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
                  <div>
                    <h2 className="font-semibold text-slate-900">Membres</h2>
                    <p className="mt-1 text-xs text-slate-500">GET /organizations/{'{id}'}/members · permission members.read</p>
                  </div>
                  <div className="flex flex-wrap items-center gap-3">
                    <label className="flex items-center gap-2 text-xs font-medium text-slate-600">
                      <input
                        type="checkbox"
                        checked={includeInactive}
                        onChange={(event) => setIncludeInactive(event.target.checked)}
                        className="h-4 w-4 rounded border-slate-300"
                      />
                      Inclure les membres désactivés
                    </label>
                    <span className="rounded-lg bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-700">API réelle</span>
                  </div>
                </div>

                <div className="border-b border-slate-100 bg-slate-50 px-5 py-3 text-xs leading-5 text-slate-600">
                  Les actions nécessitent une session active et la permission <code>members.manage</code>. Le serveur vérifie également l’origine et le jeton CSRF. La désactivation du dernier propriétaire actif est refusée.
                </div>
                {members.isLoading && <p aria-busy="true" className="p-5 text-sm text-slate-500">Chargement des membres…</p>}
                {members.isError && <div className="p-5"><AccessError error={members.error} /></div>}
                {members.data && (members.data.length === 0
                  ? <p className="p-5 text-sm text-slate-500">Aucun membre retourné par l’API.</p>
                  : <div className="overflow-x-auto"><table className="w-full min-w-[920px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3">Utilisateur</th><th className="px-5 py-3">Rôle actuel</th><th className="px-5 py-3">Statut</th><th className="px-5 py-3">Membre depuis</th><th className="px-5 py-3">Actions</th></tr></thead><tbody className="divide-y divide-slate-100">{members.data.map((member) => {
                    const selectedRoleId = roleOverrides[member.membership_id] ?? member.role_id;
                    const roleChanged = selectedRoleId !== member.role_id;
                    const isSelf = currentUser.data?.id === member.user_id;
                    return (
                      <tr key={member.membership_id}>
                        <td className="px-5 py-4"><p className="font-medium text-slate-900">{member.display_name}</p><p className="text-xs text-slate-500">{member.email}</p><p className="mt-0.5 font-mono text-[10px] text-slate-400">{member.user_id}</p></td>
                        <td className="px-5 py-4"><span className="inline-flex items-center gap-2 rounded-full bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700"><Users aria-hidden="true" className="h-3.5 w-3.5" />{member.role}</span></td>
                        <td className="px-5 py-4">{member.is_active ? <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700">Actif</span> : <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">Désactivé</span>}</td>
                        <td className="px-5 py-4 text-xs text-slate-500">{new Date(member.joined_at).toLocaleDateString("fr-FR")}</td>
                        <td className="px-5 py-4">
                          <div className="flex flex-wrap items-center gap-2">
                            <select
                              aria-label={`Nouveau rôle pour ${member.display_name}`}
                              value={selectedRoleId}
                              onChange={(event) => setRoleOverrides((current) => ({ ...current, [member.membership_id]: event.target.value }))}
                              disabled={!csrfToken || !currentUser.data || !roles.data || mutationPending}
                              className="rounded-lg border border-slate-300 bg-white px-2 py-2 text-xs disabled:bg-slate-100"
                            >
                              {(roles.data ?? []).map((role) => <option key={role.id} value={role.id}>{role.name}</option>)}
                            </select>
                            <button
                              type="button"
                              onClick={() => updateMembership.mutate({ membershipId: member.membership_id, roleId: selectedRoleId })}
                              disabled={!csrfToken || !currentUser.data || !roleChanged || mutationPending}
                              className="rounded-lg bg-accent px-3 py-2 text-xs font-semibold text-white hover:bg-accent-dark disabled:cursor-not-allowed disabled:opacity-40"
                            >
                              {updateMembership.isPending ? "Enregistrement…" : "Enregistrer"}
                            </button>
                            <button
                              type="button"
                              onClick={() => toggleStatus.mutate({ membershipId: member.membership_id, isActive: !member.is_active })}
                              disabled={!csrfToken || !currentUser.data || isSelf || mutationPending}
                              title={isSelf ? "Un membre ne peut pas changer son propre statut" : member.is_active ? "Désactiver ce membre" : "Réactiver ce membre"}
                              className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                            >
                              {toggleStatus.isPending ? "En cours…" : member.is_active ? "Désactiver" : "Réactiver"}
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                if (window.confirm(`Retirer ${member.display_name} de cette organisation ?`)) {
                                  removeMembership.mutate(member.membership_id);
                                }
                              }}
                              disabled={!csrfToken || !currentUser.data || isSelf || mutationPending}
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

              <section className="mb-5 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
                  <div>
                    <h2 className="font-semibold text-slate-900">Inviter un membre</h2>
                    <p className="mt-1 text-xs text-slate-500">POST /organizations/{'{id}'}/invitations · permission members.manage</p>
                  </div>
                  <span className="rounded-lg bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-700">API réelle</span>
                </div>
                <div className="border-b border-slate-100 bg-slate-50 px-5 py-3 text-xs leading-5 text-slate-600">
                  Aucun e-mail n’est envoyé : l’invitation est un lien manuel à copier et à transmettre à l’invité. Le lien n’est affiché qu’une seule fois, juste après la création.
                </div>
                <form
                  onSubmit={(event) => {
                    event.preventDefault();
                    if (!inviteEmail.trim() || !inviteRoleId) {
                      return;
                    }
                    createInvitation.mutate({
                      email: inviteEmail.trim().toLowerCase(),
                      roleId: inviteRoleId,
                      expiresInDays: inviteExpiryDays,
                    });
                  }}
                  className="flex flex-wrap items-end gap-3 border-b border-slate-100 px-5 py-4"
                >
                  <label className="min-w-52 flex-1 text-sm font-medium text-slate-700">
                    E-mail de l’invité
                    <input
                      type="email"
                      value={inviteEmail}
                      onChange={(event) => setInviteEmail(event.target.value)}
                      required
                      maxLength={320}
                      placeholder="nouveau@example.com"
                      className="mt-2 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm"
                    />
                  </label>
                  <label className="min-w-40 flex-1 text-sm font-medium text-slate-700">
                    Rôle
                    <select
                      value={inviteRoleId}
                      onChange={(event) => setInviteRoleId(event.target.value)}
                      required
                      disabled={!roles.data}
                      className="mt-2 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm disabled:bg-slate-100"
                    >
                      <option value="">Choisir un rôle</option>
                      {(roles.data ?? []).map((role) => <option key={role.id} value={role.id}>{role.name}</option>)}
                    </select>
                  </label>
                  <label className="w-32 text-sm font-medium text-slate-700">
                    Validité (jours)
                    <input
                      type="number"
                      value={inviteExpiryDays}
                      onChange={(event) => setInviteExpiryDays(Number(event.target.value))}
                      min={1}
                      max={30}
                      required
                      className="mt-2 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm"
                    />
                  </label>
                  <button
                    type="submit"
                    disabled={!csrfToken || !inviteEmail.trim() || !inviteRoleId || createInvitation.isPending}
                    className="rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-white hover:bg-accent-dark disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {createInvitation.isPending ? "Création…" : "Créer l’invitation"}
                  </button>
                </form>
                {createdInvitation && (
                  <div className="border-b border-slate-100 bg-emerald-50 px-5 py-4">
                    <p className="text-sm font-medium text-emerald-900">Invitation créée pour {createdInvitation.email} (rôle {createdInvitation.role_name}). Copiez ce lien maintenant : il ne sera plus affiché.</p>
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <code className="min-w-0 flex-1 break-all rounded-lg border border-emerald-200 bg-white px-3 py-2 text-xs text-slate-700">{`${typeof window !== "undefined" ? window.location.origin : ""}${createdInvitation.accept_path}`}</code>
                      <button
                        type="button"
                        onClick={copyInvitationLink}
                        className="inline-flex items-center gap-2 rounded-lg border border-emerald-300 bg-white px-3 py-2 text-xs font-semibold text-emerald-800 hover:bg-emerald-100"
                      >
                        <Copy aria-hidden="true" className="h-4 w-4" />
                        {copiedLink ? "Lien copié" : "Copier le lien"}
                      </button>
                    </div>
                  </div>
                )}
                {invitations.isLoading && <p aria-busy="true" className="p-5 text-sm text-slate-500">Chargement des invitations…</p>}
                {invitations.isError && <div className="p-5"><AccessError error={invitations.error} /></div>}
                {invitations.data && (invitations.data.length === 0
                  ? <p className="p-5 text-sm text-slate-500">Aucune invitation pour cette organisation.</p>
                  : <ul className="divide-y divide-slate-100">{invitations.data.map((invitation) => (
                    <li key={invitation.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
                      <div className="min-w-0">
                        <p className="font-medium text-slate-900">{invitation.email}</p>
                        <p className="text-xs text-slate-500">Rôle {invitation.role_name} · expire le {new Date(invitation.expires_at).toLocaleDateString("fr-FR")} · {invitationStatusLabel(invitation)}</p>
                      </div>
                      {invitation.status === "pending" && (
                        <button
                          type="button"
                          onClick={() => {
                            if (window.confirm(`Révoquer l’invitation de ${invitation.email} ?`)) {
                              revokeInvitation.mutate(invitation.id);
                            }
                          }}
                          disabled={!csrfToken || revokeInvitation.isPending}
                          className="rounded-lg border border-rose-200 px-3 py-2 text-xs font-semibold text-rose-700 hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-40"
                        >
                          {revokeInvitation.isPending ? "Révocation…" : "Révoquer"}
                        </button>
                      )}
                    </li>
                  ))}</ul>
                )}
              </section>

              <section className="mb-5 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
                  <div>
                    <h2 className="font-semibold text-slate-900">Ajouter un membre existant</h2>
                    <p className="mt-1 text-xs text-slate-500">POST /organizations/{'{id}'}/memberships · permission members.manage</p>
                  </div>
                  <span className="rounded-lg bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-700">API réelle</span>
                </div>
                <form
                  onSubmit={(event) => {
                    event.preventDefault();
                    if (!newMemberUserId.trim() || !newMemberRoleId) {
                      return;
                    }
                    addMembership.mutate({
                      userId: newMemberUserId.trim(),
                      roleId: newMemberRoleId,
                    });
                  }}
                  className="flex flex-wrap items-end gap-3 px-5 py-4"
                >
                  <label className="min-w-64 flex-1 text-sm font-medium text-slate-700">
                    Identifiant utilisateur (UUID)
                    <input
                      type="text"
                      value={newMemberUserId}
                      onChange={(event) => setNewMemberUserId(event.target.value)}
                      required
                      placeholder="00000000-0000-0000-0000-000000000000"
                      className="mt-2 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 font-mono text-sm"
                    />
                    <span className="mt-1 block text-xs font-normal text-slate-500">
                      L’identifiant est affiché sous l’e-mail de chaque membre du tableau ci-dessus.
                    </span>
                  </label>
                  <label className="min-w-40 flex-1 text-sm font-medium text-slate-700">
                    Rôle
                    <select
                      value={newMemberRoleId}
                      onChange={(event) => setNewMemberRoleId(event.target.value)}
                      required
                      disabled={!roles.data}
                      className="mt-2 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm disabled:bg-slate-100"
                    >
                      <option value="">Choisir un rôle</option>
                      {(roles.data ?? []).map((role) => <option key={role.id} value={role.id}>{role.name}</option>)}
                    </select>
                  </label>
                  <button
                    type="submit"
                    disabled={!csrfToken || !newMemberUserId.trim() || !newMemberRoleId || addMembership.isPending}
                    className="rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-white hover:bg-accent-dark disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {addMembership.isPending ? "Ajout…" : "Ajouter le membre"}
                  </button>
                </form>
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

              <p className="mt-4 text-xs text-slate-400">Les rôles personnalisés ne sont pas implémentés dans ce lot : seuls les quatre rôles système sont disponibles.</p>
            </>
          )}
        </>
      )}
    </AppShell>
  );
}

export default function UsersPage() {
  return (
    <Suspense fallback={<main aria-busy="true" className="p-6 text-sm text-slate-500">Chargement des paramètres…</main>}>
      <UsersPageContent />
    </Suspense>
  );
}
