"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { PageHeading } from "@/components/page-heading";
import { useCsrfToken } from "@/lib/csrf-token";
import {
  OrganizationApiError,
  createOrganization,
} from "@/lib/organization-api";

export default function NewOrganisationPage() {
  const router = useRouter();
  const csrfToken = useCsrfToken();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [error, setError] = useState("");
  const [isPending, setIsPending] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    if (!csrfToken) {
      setError("Session non initialisée dans ce navigateur. Reconnectez-vous.");
      return;
    }
    setIsPending(true);
    try {
      const organization = await createOrganization(
        name.trim(),
        slug.trim().toLowerCase(),
        csrfToken,
      );
      router.push(`/users?organization=${encodeURIComponent(organization.id)}`);
    } catch (caught) {
      if (caught instanceof OrganizationApiError && caught.status === 409) {
        setError("Ce slug est déjà utilisé par une autre organisation.");
      } else if (
        caught instanceof OrganizationApiError &&
        caught.status === 422
      ) {
        setError(
          "Slug invalide : minuscules, chiffres et tirets uniquement, sans tiret au début ni à la fin.",
        );
      } else if (
        caught instanceof OrganizationApiError &&
        caught.status === 401
      ) {
        setError("Session expirée. Reconnectez-vous avant de créer une organisation.");
      } else {
        setError("La création a échoué. Vérifiez l’API puis réessayez.");
      }
    } finally {
      setIsPending(false);
    }
  }

  return (
    <AppShell>
      <PageHeading
        eyebrow="Administration"
        title="Nouvelle organisation"
        description="Créez un espace, ses quatre rôles système et votre membership de propriétaire en une seule opération."
      />

      <section className="max-w-xl overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <form onSubmit={handleSubmit} className="space-y-4 px-5 py-5">
          <label className="block text-sm font-medium text-slate-700">
            Nom de l’organisation
            <input
              type="text"
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
              maxLength={255}
              placeholder="Acme Corp"
              className="mt-2 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm"
            />
          </label>
          <label className="block text-sm font-medium text-slate-700">
            Slug (identifiant unique, minuscules et tirets)
            <input
              type="text"
              value={slug}
              onChange={(event) => setSlug(event.target.value)}
              required
              maxLength={255}
              placeholder="acme"
              className="mt-2 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm"
            />
            <span className="mt-1 block text-xs font-normal text-slate-500">
              Le slug est immuable une fois l’organisation créée.
            </span>
          </label>
          {!csrfToken && (
            <p role="alert" className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
              Session non initialisée dans ce navigateur. <Link className="font-semibold underline" href="/login">Reconnectez-vous</Link> pour créer une organisation.
            </p>
          )}
          {error && (
            <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
              {error}
            </p>
          )}
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="submit"
              disabled={!csrfToken || isPending || !name.trim() || !slug.trim()}
              className="rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-white hover:bg-accent-dark disabled:cursor-not-allowed disabled:opacity-40"
            >
              {isPending ? "Création…" : "Créer l’organisation"}
            </button>
            <Link href="/organisations" className="rounded-lg border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50">
              Annuler
            </Link>
          </div>
        </form>
      </section>
    </AppShell>
  );
}
