"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Building2,
  LayoutDashboard,
  ScrollText,
  Server,
  Users,
} from "lucide-react";

const navigation = [
  { href: "/", label: "Vue d'ensemble", icon: LayoutDashboard },
  { href: "/organisations", label: "Organisations", icon: Building2 },
  { href: "/users", label: "Utilisateurs & rôles", icon: Users },
  { href: "/infrastructure", label: "Infrastructure", icon: Server },
  { href: "/audit", label: "Événements & audit", icon: ScrollText },
] as const;

export function SidebarNav() {
  const pathname = usePathname();

  return (
    <nav aria-label="Navigation principale" className="space-y-1 px-3">
      {navigation.map(({ href, label, icon: Icon }) => {
        const active =
          href === "/" ? pathname === "/" : pathname.startsWith(href);

        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={`group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
              active
                ? "bg-white/10 text-white shadow-sm"
                : "text-slate-400 hover:bg-white/5 hover:text-slate-100"
            }`}
          >
            <Icon
              aria-hidden="true"
              className={`h-4 w-4 shrink-0 ${
                active ? "text-blue-300" : "text-slate-500 group-hover:text-slate-300"
              }`}
            />
            <span>{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
