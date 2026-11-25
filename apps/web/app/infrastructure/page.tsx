import { Activity, Cpu, HardDrive, Server } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { PageHeading } from "@/components/page-heading";
import { demoAssets, demoNotice } from "@/lib/demo-data";

function UsageBar({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between text-xs">
        <span className="text-slate-500">{label}</span>
        <span className="font-medium tabular-nums text-slate-700">{value}%</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
        <div
          className="h-full rounded-full bg-accent"
          style={{ width: `${value}%` }}
        />
      </div>
    </div>
  );
}

export default function InfrastructurePage() {
  return (
    <AppShell>
      <PageHeading
        eyebrow="Supervision"
        title="Infrastructure"
        description="Inventaire et état des ressources présentés dans un scénario simulé."
      />

      <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        <strong>Connecteurs simulés.</strong> {demoNotice}
      </div>

      <div className="mb-5 flex flex-wrap gap-3">
        <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
          <p className="text-xs text-slate-500">Ressources affichées</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums text-slate-900">
            {demoAssets.length.toString().padStart(2, "0")}
          </p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
          <p className="text-xs text-slate-500">À surveiller</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums text-amber-600">
            {demoAssets.filter((asset) => asset.status === "À surveiller").length}
          </p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
          <p className="text-xs text-slate-500">Hors ligne</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums text-slate-700">
            {demoAssets.filter((asset) => asset.status === "Hors ligne").length}
          </p>
        </div>
      </div>

      <section className="grid gap-4 xl:grid-cols-2">
        {demoAssets.map((asset) => (
          <article
            key={asset.name}
            className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-slate-600">
                  <Server aria-hidden="true" className="h-5 w-5" />
                </div>
                <div>
                  <h2 className="font-semibold text-slate-900">{asset.name}</h2>
                  <p className="mt-0.5 text-xs text-slate-500">
                    {asset.kind} · {asset.location}
                  </p>
                </div>
              </div>
              <span
                className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                  asset.status === "Opérationnel"
                    ? "bg-emerald-50 text-emerald-700"
                    : asset.status === "À surveiller"
                      ? "bg-amber-50 text-amber-700"
                      : "bg-slate-100 text-slate-600"
                }`}
              >
                {asset.status}
              </span>
            </div>

            <div className="mt-5 grid gap-4 sm:grid-cols-2">
              <UsageBar label="CPU" value={asset.cpu} />
              <UsageBar label="Mémoire" value={asset.memory} />
            </div>

            <div className="mt-5 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-4 text-xs text-slate-500">
              <span className="inline-flex items-center gap-1.5">
                <Activity aria-hidden="true" className="h-3.5 w-3.5" />
                {asset.environment}
              </span>
              <span>Dernier signal : {asset.lastSeen}</span>
            </div>
          </article>
        ))}
      </section>
      <p className="mt-5 text-xs text-slate-400">
        <Cpu aria-hidden="true" className="mr-1 inline h-3.5 w-3.5" />
        <HardDrive aria-hidden="true" className="mr-1 inline h-3.5 w-3.5" />
        Les métriques CPU et mémoire sont des valeurs d'exemple, non collectées en temps réel.
      </p>
    </AppShell>
  );
}
