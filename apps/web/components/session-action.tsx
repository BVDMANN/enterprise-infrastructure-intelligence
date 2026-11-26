"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { logout } from "@/lib/api";

export function SessionAction() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [csrfToken, setCsrfToken] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setCsrfToken(window.sessionStorage.getItem("eii_csrf_token"));
  }, []);

  async function signOut() {
    if (!csrfToken) return;
    setPending(true);
    setError("");
    try {
      await logout(csrfToken);
      window.sessionStorage.removeItem("eii_csrf_token");
      queryClient.clear();
      setCsrfToken(null);
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

  return (
    <div className="flex items-center gap-2">
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
