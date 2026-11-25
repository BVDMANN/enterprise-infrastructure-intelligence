import { AlertTriangle, Info, ShieldAlert } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { PageHeading } from "@/components/page-heading";
import { demoEvents, demoNotice } from "@/lib/demo-data";

export default function AuditPage() {
  return (
    <AppShell>
      <PageHeading
        eyebrow="Traçabilité"
        title="Événements & audit"
        description="Journal de démonstration des événements de supervision et des opérations."
      />

      <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        <strong>Journal simulé.</strong> {demoNotice} Aucun événement de sécurité réel n&apos;est enregistré à ce stade.
      </div>

      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-100 px-5 py-4">
          <h2 className="font-semibold text-slate-900">Activité récente</h2>
          <p className="mt-1 text-xs text-slate-500">
            {demoEvents.length} événements fictifs · journal backend à implémenter
          </p>
        </div>
        <ol className="divide-y divide-slate-100">
          {demoEvents.map((event, index) => {
            const Icon =
              event.level === "Critique"
                ? ShieldAlert
                : event.level === "Avertissement"
                  ? AlertTriangle
                  : Info;
            const iconStyle =
              event.level === "Critique"
                ? "bg-rose-50 text-rose-600"
                : event.level === "Avertissement"
                  ? "bg-amber-50 text-amber-600"
                  : "bg-blue-50 text-blue-600";

            return (
              <li key={`${event.time}-${index}`} className="flex gap-4 px-5 py-5">
                <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${iconStyle}`}>
                  <Icon aria-hidden="true" className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-medium text-slate-900">{event.title}</p>
                    <span className="text-xs tabular-nums text-slate-400">
                      {event.date} · {event.time}
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-slate-600">{event.detail}</p>
                  <p className="mt-2 text-xs text-slate-400">
                    {event.actor} · {event.level}
                  </p>
                </div>
              </li>
            );
          })}
        </ol>
      </section>
    </AppShell>
  );
}
