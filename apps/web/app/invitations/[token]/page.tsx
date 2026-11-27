"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ApiError, getCurrentUser, logout } from "@/lib/api";
import { clearCsrfToken, useCsrfToken } from "@/lib/csrf-token";
import {
  InvitationApiError,
  acceptInvitation,
  previewInvitation,
} from "@/lib/invitation-api";

export default function InvitationAcceptPage() {
  const params = useParams();
  const token = params.token as string;
  const csrfToken = useCsrfToken();
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isPending, setIsPending] = useState(false);
  const [accepted, setAccepted] = useState<{
    organization_name: string;
    role_name: string;
  } | null>(null);

  const preview = useQuery({
    queryKey: ["invitation-preview", token],
    queryFn: () => previewInvitation(token),
    retry: false,
  });

  const currentUser = useQuery({
    queryKey: ["current-user"],
    queryFn: getCurrentUser,
    enabled: Boolean(csrfToken),
    retry: false,
    staleTime: 30_000,
  });

  const sessionEmail = currentUser.data?.email ?? null;
  const isInviteeSession =
    sessionEmail !== null && preview.data?.email === sessionEmail;
  const isOtherSession =
    sessionEmail !== null && preview.data?.email !== sessionEmail;

  async function acceptAsInvitee() {
    setError("");
    setIsPending(true);
    try {
      const result = await acceptInvitation(token, {}, csrfToken ?? undefined);
      setAccepted({
        organization_name: result.organization_name,
        role_name: result.role_name,
      });
    } catch (caught) {
      handleAcceptError(caught);
    } finally {
      setIsPending(false);
    }
  }

  async function acceptWithPassword(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    setIsPending(true);
    try {
      const result = await acceptInvitation(
        token,
        { display_name: displayName.trim(), password },
        csrfToken ?? undefined,
      );
      setAccepted({
        organization_name: result.organization_name,
        role_name: result.role_name,
      });
    } catch (caught) {
      handleAcceptError(caught);
    } finally {
      setIsPending(false);
    }
  }

  function handleAcceptError(caught: unknown) {
    if (caught instanceof InvitationApiError && caught.status === 401) {
      setError("Mot de passe incorrect.");
    } else if (caught instanceof InvitationApiError && caught.status === 403) {
      setError("Cette invitation est adressée à une autre adresse e-mail.");
    } else if (caught instanceof InvitationApiError && caught.status === 404) {
      setError("Invitation introuvable, expirée ou déjà utilisée.");
    } else if (caught instanceof InvitationApiError && caught.status === 409) {
      setError("Vous êtes déjà membre de cette organisation.");
    } else if (caught instanceof InvitationApiError && caught.status === 422) {
      setError(caught.message);
    } else {
      setError("L’acceptation a échoué. Vérifiez l’API puis réessayez.");
    }
  }

  async function switchAccount() {
    if (!csrfToken) {
      return;
    }
    try {
      await logout(csrfToken);
    } catch (caught) {
      if (!(caught instanceof ApiError)) {
        throw caught;
      }
      // A stale session is already gone: continue to the password form.
    } finally {
      clearCsrfToken();
      currentUser.refetch();
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-5 py-12">
      <section className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-7 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">
          Enterprise Infrastructure Intelligence
        </p>
        <h1 className="mt-3 text-2xl font-semibold tracking-tight text-slate-950">
          Invitation à rejoindre une organisation
        </h1>

        {preview.isLoading && (
          <p aria-busy="true" className="mt-4 text-sm text-slate-500">
            Chargement de l’invitation…
          </p>
        )}
        {preview.isError && (
          <p role="alert" className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
            Invitation introuvable, expirée, révoquée ou déjà acceptée. Demandez un nouveau lien à l’administrateur de l’organisation.
          </p>
        )}

        {preview.data && !accepted && (
          <>
            <p className="mt-2 text-sm leading-6 text-slate-500">
              Vous êtes invité à rejoindre <strong className="text-slate-900">{preview.data.organization_name}</strong> ({preview.data.organization_slug}) avec le rôle <strong className="text-slate-900">{preview.data.role_name}</strong>. L’invitation est adressée à <strong className="text-slate-900">{preview.data.email}</strong> et expire le {new Date(preview.data.expires_at).toLocaleDateString("fr-FR")}.
            </p>

            {isInviteeSession && (
              <div className="mt-6">
                <p className="text-sm text-slate-600">
                  Vous êtes connecté en tant que {sessionEmail}.
                </p>
                <button
                  type="button"
                  onClick={acceptAsInvitee}
                  disabled={isPending}
                  className="mt-3 w-full rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-white hover:bg-accent-dark disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {isPending ? "Acceptation…" : "Accepter l’invitation"}
                </button>
              </div>
            )}

            {isOtherSession && (
              <div className="mt-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
                <p>
                  Vous êtes connecté en tant que {sessionEmail}, mais cette invitation est adressée à {preview.data.email}.
                </p>
                <button
                  type="button"
                  onClick={switchAccount}
                  className="mt-3 rounded-lg border border-amber-300 bg-white px-3 py-2 text-xs font-semibold text-amber-900 hover:bg-amber-100"
                >
                  Se déconnecter pour accepter avec un autre compte
                </button>
              </div>
            )}

            {!isInviteeSession && !isOtherSession && (
              <form onSubmit={acceptWithPassword} className="mt-6 space-y-4">
                <p className="text-sm text-slate-600">
                  {sessionEmail
                    ? "Votre session n’est plus valide : acceptez avec votre mot de passe."
                    : "Acceptez avec votre mot de passe. Si vous n’avez pas encore de compte, il sera créé avec le nom affiché ci-dessous."}
                </p>
                <label className="block text-sm font-medium text-slate-700">
                  Nom affiché (compte à créer uniquement)
                  <input
                    type="text"
                    value={displayName}
                    onChange={(event) => setDisplayName(event.target.value)}
                    maxLength={255}
                    placeholder="Prénom Nom"
                    autoComplete="name"
                    className="mt-2 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm"
                  />
                </label>
                <label className="block text-sm font-medium text-slate-700">
                  Mot de passe
                  <input
                    type="password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    required
                    minLength={12}
                    autoComplete="current-password"
                    className="mt-2 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm"
                  />
                  <span className="mt-1 block text-xs font-normal text-slate-500">
                    12 caractères minimum.
                  </span>
                </label>
                {error && (
                  <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
                    {error}
                  </p>
                )}
                <button
                  type="submit"
                  disabled={isPending || !password}
                  className="w-full rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-white hover:bg-accent-dark disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {isPending ? "Acceptation…" : "Accepter l’invitation"}
                </button>
              </form>
            )}

            {isInviteeSession && error && (
              <p role="alert" className="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
                {error}
              </p>
            )}
          </>
        )}

        {accepted && (
          <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-4">
            <p className="text-sm font-medium text-emerald-900">
              Invitation acceptée : vous êtes désormais membre de {accepted.organization_name} avec le rôle {accepted.role_name}.
            </p>
            <p className="mt-2 text-sm text-emerald-800">
              Connectez-vous pour accéder à votre organisation.
            </p>
            <Link href="/login" className="mt-3 inline-flex rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-white hover:bg-accent-dark">
              Se connecter
            </Link>
          </div>
        )}
      </section>
    </main>
  );
}
