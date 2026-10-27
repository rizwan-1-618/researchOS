"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import type { User } from "@/lib/types";
import { useRefresh } from "@/components/ui";

const links = [
  ["Desk", "/app"],
  ["Discover", "/app/discover"],
  ["Library", "/app/library"],
  ["Collections", "/app/collections"],
  ["Projects", "/app/projects"],
  ["Questions", "/app/questions"],
  ["Tasks", "/app/tasks"],
  ["Notes", "/app/notes"],
  ["Concepts", "/app/concepts"],
  ["Graph", "/app/graph"],
  ["Analytics", "/app/analytics"],
  ["Profile", "/app/profile"],
];

export function Shell({ user, children }: { user: User; children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const refresh = useRefresh();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  async function logout() {
    await api("/api/auth/logout", { method: "POST" });
    await refresh();
    router.push("/login");
  }

  return (
    <div className="min-h-screen md:grid md:grid-cols-[240px_1fr]">
      <aside className={`${open ? "block" : "hidden"} bg-sidebar text-paper md:sticky md:top-0 md:block md:h-screen md:self-start md:overflow-y-auto`}>
        <div className="flex h-full min-h-screen flex-col px-5 py-6 md:min-h-full">
          <Link href="/app" className="serif text-3xl tracking-tight">
            ResearchOS
          </Link>
          <p className="mt-1 text-xs uppercase tracking-[0.18em] text-paper/50">Reading room</p>
          <nav className="mt-8 flex flex-1 flex-col gap-1">
            {links.map(([name, href]) => {
              const active = href === "/app" ? pathname === href : pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  onClick={() => setOpen(false)}
                  className={`rounded-xl px-3 py-2 text-sm ${active ? "bg-paper text-ink" : "text-paper/75 hover:bg-white/5"}`}
                >
                  {name}
                </Link>
              );
            })}
          </nav>
          <div className="border-t border-white/10 pt-4">
            <p className="truncate text-sm">{user.name}</p>
            <button className="mt-2 text-sm text-paper/60" onClick={logout} type="button">
              Sign out
            </button>
          </div>
        </div>
      </aside>
      <div className="min-w-0">
        <header className="sticky top-0 z-20 flex items-center gap-3 border-b border-black/[0.06] bg-[#f3efe6]/90 px-4 py-3 backdrop-blur md:px-8">
          <button className="rounded-full border border-black/[0.08] bg-white px-3 py-1 text-sm md:hidden" onClick={() => setOpen((value) => !value)} type="button">
            Menu
          </button>
          <form
            className="w-full max-w-md"
            onSubmit={(event) => {
              event.preventDefault();
              if (query.trim()) router.push(`/app/discover?q=${encodeURIComponent(query.trim())}`);
            }}
          >
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search the literature"
              className="w-full rounded-full border border-black/[0.08] bg-white px-4 py-2 text-sm outline-none focus:border-[#17171a]"
            />
          </form>
        </header>
        <main className="px-4 py-6 md:px-8 md:py-8">{children}</main>
      </div>
    </div>
  );
}
