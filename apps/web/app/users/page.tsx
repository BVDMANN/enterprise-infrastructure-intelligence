import { UserRound, ShieldCheck } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { PageHeading } from "@/components/page-heading";
import { demoNotice, demoUsers } from "@/lib/demo-data";

export default function UsersPage() {
  return (
    <AppShell>
      <PageHeading
        eyebrow="Administration"
        title="Utilisateurs & rôles"
        description="Aperçu des comptes, de leur organisation et de leur niveau d'accès."
      />

      <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        <strong>Mode démonstration.</strong> {demoNotice}
      </div>

      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
          <div>
            <h2 className="font-semibold text-slate-900">Comptes utilisateurs</h2>
            <p className="mt-1 text-xs text-slate-500">
              {demoUsers.length} profils fictifs · RBAC serveur en cours de construction
            </p>
          </div>
          <span className="rounded-lg bg-slate-100 px-3 py-2 text-xs font-medium text-slate-500">
            Invitations désactivées
          </span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-5 py-3 font-semibold">Utilisateur</th>
                <th className="px-5 py-3 font-semibold">Organisation</th>
                <th className="px-5 py-3 font-semibold">Rôle affiché</th>
                <th className="px-5 py-3 font-semibold">État du compte</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {demoUsers.map((user) => (
                <tr key={user.email} className="hover:bg-slate-50/80">
                  <td className="px-5 py-4">
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-100 text-slate-500">
                        <UserRound aria-hidden="true" className="h-4 w-4" />
                      </div>
                      <div>
                        <p className="font-medium text-slate-900">{user.name}</p>
                        <p className="text-xs text-slate-400">{user.email}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-5 py-4 text-slate-600">{user.organization}</td>
                  <td className="px-5 py-4">
                    <span className="inline-flex items-center gap-2 rounded-full bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700">
                      <ShieldCheck aria-hidden="true" className="h-3.5 w-3.5" />
                      {user.role}
                    </span>
                  </td>
                  <td className="px-5 py-4">
                    <span
                      className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                        user.status === "Actif"
                          ? "bg-emerald-50 text-emerald-700"
                          : "bg-amber-50 text-amber-700"
                      }`}
                    >
                      {user.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </AppShell>
  );
}
