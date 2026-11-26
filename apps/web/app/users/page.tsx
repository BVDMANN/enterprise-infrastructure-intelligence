"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ShieldCheck, Users } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { PageHeading } from "@/components/page-heading";
import {
  ApiError,
  getOrganizationMembers,
  getOrganizationRoles,
  getOrganizations,
} from "@/lib/api";

function AccessError({ error }: { error: unknown }) {
  if (error instanceof ApiError && error.status === 401) {
    return <p role="alert" className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">Session requise. <Link className="font-semibold underline" href="/login">Se connecter</Link>.</p>;
  }
  if (error instanceof ApiError && error.status === 403) {
    return <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">Accès refusé : votre membership ne possède pas la permission demandée.</p>;
  }
  if (error instanceof ApiError && error.status === 404) {
    return <p role="alert" className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">Organisation introuvable ou non accessible avec cette session.</p>;
  }
  return <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">Erreur lors de la lecture de l'API. Vérifiez le Control Plane puis réessayez.</p>;
}

export default function UsersPage() {
  const [selectedOrganizationId, setSelectedOrganizationId] = useState("");
  const organizations = useQuery({
    queryKey: ["organizations"],
    queryFn: getOrganizations,
    retry: false,
  });
  const organizationId =
    selectedOrganizationId || organizations.data?.[0]?.id || "";

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
                  onChange={(event) => setSelectedOrganizationId(event.target.value)}
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
                {members.isLoading && <p aria-busy="true" className="p-5 text-sm text-slate-500">Chargement des membres…</p>}
                {members.isError && <div className="p-5"><AccessError error={members.error} /></div>}
                {members.data && (members.data.length === 0
                  ? <p className="p-5 text-sm text-slate-500">Aucun membre actif retourné par l'API.</p>
                  : <div className="overflow-x-auto"><table className="w-full min-w-[600px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3">Utilisateur</th><th className="px-5 py-3">Rôle</th><th className="px-5 py-3">Membre depuis</th></tr></thead><tbody className="divide-y divide-slate-100">{members.data.map((member) => <tr key={member.user_id}><td className="px-5 py-4"><p className="font-medium text-slate-900">{member.display_name}</p><p className="text-xs text-slate-500">{member.email}</p></td><td className="px-5 py-4"><span className="inline-flex items-center gap-2 rounded-full bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700"><Users aria-hidden="true" className="h-3.5 w-3.5" />{member.role}</span></td><td className="px-5 py-4 text-xs text-slate-500">{new Date(member.joined_at).toLocaleDateString("fr-FR")}</td></tr>)}</tbody></table></div>
                )}
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

              <p className="mt-4 text-xs text-slate-400">Lecture seule : invitations, création de comptes et changement de rôle ne sont pas encore implémentés.</p>
            </>
          )}
        </>
      )}
    </AppShell>
  );
}
