import { Building2, Users, Server } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { PageHeading } from "@/components/page-heading";
import { demoNotice, demoOrganizations } from "@/lib/demo-data";

export default function OrganisationsPage() {
  return (
    <AppShell>
      <PageHeading
        eyebrow="Administration"
        title="Organisations"
        description="Vue de démonstration des espaces clients et de leurs périmètres."
      />

      <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        <strong>Mode démonstration.</strong> {demoNotice}
      </div>

      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
          <div>
            <h2 className="font-semibold text-slate-900">Espaces clients</h2>
            <p className="mt-1 text-xs text-slate-500">
              {demoOrganizations.length} organisations fictives
            </p>
          </div>
          <span className="rounded-lg bg-slate-100 px-3 py-2 text-xs font-medium text-slate-500">
            Gestion non activée
          </span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[680px] text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-5 py-3 font-semibold">Organisation</th>
                <th className="px-5 py-3 font-semibold">Membres</th>
                <th className="px-5 py-3 font-semibold">Ressources</th>
                <th className="px-5 py-3 font-semibold">Statut</th>
                <th className="px-5 py-3 font-semibold">Dernière activité</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {demoOrganizations.map((organization) => (
                <tr key={organization.slug} className="hover:bg-slate-50/80">
                  <td className="px-5 py-4">
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-50 text-accent">
                        <Building2 aria-hidden="true" className="h-4 w-4" />
                      </div>
                      <div>
                        <p className="font-medium text-slate-900">
                          {organization.name}
                        </p>
                        <p className="text-xs text-slate-400">
                          {organization.slug}
                        </p>
                      </div>
                    </div>
                  </td>
                  <td className="px-5 py-4 text-slate-600">
                    <span className="inline-flex items-center gap-2">
                      <Users className="h-4 w-4 text-slate-400" />
                      {organization.members}
                    </span>
                  </td>
                  <td className="px-5 py-4 text-slate-600">
                    <span className="inline-flex items-center gap-2">
                      <Server className="h-4 w-4 text-slate-400" />
                      {organization.assets}
                    </span>
                  </td>
                  <td className="px-5 py-4">
                    <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700">
                      {organization.status}
                    </span>
                  </td>
                  <td className="px-5 py-4 text-xs text-slate-500">
                    {organization.updated}
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
