import { Bell, ShieldCheck } from "lucide-react";
import { SidebarNav } from "./sidebar-nav";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 flex-col border-r border-white/10 bg-navy-950 text-slate-200 lg:flex">
        <div className="flex h-20 items-center gap-3 border-b border-white/10 px-6">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500/15 text-blue-300">
            <ShieldCheck aria-hidden="true" className="h-6 w-6" />
          </div>
          <div>
            <p className="text-sm font-semibold tracking-[0.18em] text-white">
              EII
            </p>
            <p className="mt-0.5 text-[10px] font-medium tracking-[0.16em] text-slate-500">
              CONTROL PLANE
            </p>
          </div>
        </div>

        <div className="px-6 pb-3 pt-7">
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
            Espace de travail
          </p>
        </div>
        <SidebarNav />

        <div className="mt-auto p-4">
          <div className="rounded-xl border border-white/10 bg-white/5 p-3">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-amber-400" />
              <p className="text-xs font-semibold text-slate-200">
                Environnement de démo
              </p>
            </div>
            <p className="mt-2 text-[11px] leading-5 text-slate-500">
              Les données métier affichées sont simulées. Aucune infrastructure
              client n'est connectée.
            </p>
          </div>
          <p className="px-2 pt-4 text-[10px] text-slate-600">
            EII · Version de démonstration
          </p>
        </div>
      </aside>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-slate-200 bg-white/95 px-5 backdrop-blur md:px-8">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
              Enterprise Infrastructure Intelligence
            </p>
            <p className="mt-0.5 text-sm font-medium text-slate-700">
              Console d'administration
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-[10px] font-bold tracking-[0.12em] text-amber-800">
              MODE DÉMO
            </span>
            <div
              aria-label="Notifications non activées dans la démonstration"
              title="Notifications non activées dans la démonstration"
              className="flex h-9 w-9 items-center justify-center rounded-full border border-slate-200 text-slate-400"
            >
              <Bell aria-hidden="true" className="h-4 w-4" />
            </div>
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-navy-900 text-xs font-semibold text-white">
              EII
            </div>
          </div>
        </header>

        <main className="mx-auto max-w-7xl px-5 py-8 md:px-8 lg:px-10">
          {children}
        </main>
      </div>
    </div>
  );
}
