"use client";

import { Activity, FileStack, Settings } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/dashboard", label: "Documents", icon: FileStack },
  { href: "/activity", label: "Activity", icon: Activity },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function AppNav({ onNavigate, pathname: pathnameOverride }: { onNavigate?: (href: string) => void; pathname?: string }) {
  const livePath = usePathname();
  const pathname = pathnameOverride ?? livePath;
  return (
    <nav className="flex flex-col gap-1">
      {LINKS.map((link) => {
        const active =
          link.href === "/dashboard"
            ? pathname.startsWith("/dashboard") || pathname.startsWith("/documents")
            : pathname === link.href || pathname.startsWith(`${link.href}/`);
        const Icon = link.icon;
        return (
          <Link
            key={link.href}
            href={link.href}
            onClick={() => onNavigate?.(link.href)}
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2.5 text-base transition-colors duration-200",
              active ? "bg-sidebar-accent text-sidebar-foreground" : "text-sidebar-foreground/75 hover:bg-sidebar-accent hover:text-sidebar-foreground",
            )}
          >
            <Icon className="h-4 w-4" />
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}
