"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, getCurrentUser, logout } from "@/lib/api";
import { clearCsrfToken, useCsrfToken } from "@/lib/csrf-token";

export function SessionAction() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const csrfToken = useCsrfToken();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  const {
    data: user,
    isPending: checkingSession,
    error: sessionError,
  } = useQuery({
    queryKey: ["current-user"],
    queryFn: getCurrentUser,
    enabled: Boolean(csrfToken),
    retry: false,
    staleTime: 30_000,
  });


  async function signOut() {
    if (!csrfToken) return;
    setPending(true);
    setError("");
    try {
      await logout(csrfToken);
      clearCsrfToken();
      queryClient.clear();
      router.replace("/login");
    } catch {
      setError("Déconnexion refusée. La session ou le jeton CSRF a peut-être expiré.");
    } finally {
      setPending(false);
    }
  }

  if (!csrfToken) {
    return (
      <Link
        href="/login"
        className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
      >
        Connexion
      </Link>
    );
  }

  if (checkingSession) {
    return (
      <span aria-live="polite" className="text-xs text-slate-500">
        Vérification de la session…
      </span>
    );
  }

  if (sessionError) {
    if (sessionError instanceof ApiError && sessionError.status === 401) {
      return (
        <Link
          href="/login"
          className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
        >
          Session expirée — connexion
        </Link>
      );
    }
    return (
      <span role="alert" className="text-xs text-rose-600">
        Impossible de vérifier la session.
      </span>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <span className="hidden text-xs text-slate-500 sm:inline">
        {user?.display_name ?? "Session active"}
      </span>
      {error && (
        <span role="alert" className="hidden text-xs text-rose-600 md:inline">
          {error}
        </span>
      )}
      <button
        type="button"
        onClick={() => void signOut()}
        disabled={pending}
        className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
      >
        {pending ? "Déconnexion…" : "Déconnexion"}
      </button>
    </div>
  );
}
