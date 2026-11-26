"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ApiError, login } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setPending(true);
    try {
      const result = await login(email.trim(), password);
      window.sessionStorage.setItem("eii_csrf_token", result.csrf_token);
      router.replace("/organisations");
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 401) {
        setError("Adresse e-mail ou mot de passe incorrect.");
      } else if (caught instanceof ApiError && caught.status === 429) {
        setError("Trop de tentatives. Réessayez dans quelques minutes.");
      } else {
        setError("Connexion impossible. Vérifiez l'API et la configuration CORS.");
      }
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-5 py-12">
      <section className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-7 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">Enterprise Infrastructure Intelligence</p>
        <h1 className="mt-3 text-2xl font-semibold tracking-tight text-slate-950">Connexion</h1>
        <p className="mt-2 text-sm leading-6 text-slate-500">Authentification locale par session serveur. Le cookie de session reste HttpOnly et n'est jamais lu par le navigateur JavaScript.</p>
        <form onSubmit={submit} className="mt-6 space-y-4">
          <label className="block text-sm font-medium text-slate-700">Adresse e-mail
            <input type="email" required autoComplete="username" value={email} onChange={(event) => setEmail(event.target.value)} className="mt-2 block w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm" />
          </label>
          <label className="block text-sm font-medium text-slate-700">Mot de passe
            <input type="password" required autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} className="mt-2 block w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm" />
          </label>
          {error && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
          <button type="submit" disabled={pending} className="w-full rounded-lg bg-accent px-4 py-3 text-sm font-semibold text-white hover:bg-accent-dark disabled:cursor-not-allowed disabled:opacity-60">{pending ? "Connexion…" : "Se connecter"}</button>
        </form>
        <p className="mt-5 text-xs leading-5 text-slate-400">Un administrateur doit avoir initialisé un compte via le bootstrap documenté. Aucun compte de démonstration ni mot de passe fictif n'est fourni.</p>
        <Link href="/" className="mt-5 inline-block text-sm font-medium text-accent hover:underline">Retour au tableau de bord</Link>
      </section>
    </main>
  );
}
