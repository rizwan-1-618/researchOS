"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Shell } from "@/components/shell";
import { api } from "@/lib/api";
import type { User } from "@/lib/types";

export default function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const me = useQuery({ queryKey: ["me"], queryFn: () => api<User>("/api/auth/me"), retry: false });

  useEffect(() => {
    if (me.isError) router.replace("/login");
  }, [me.isError, router]);

  if (!me.data) {
    return <div className="grid min-h-screen place-items-center text-soft">Opening the desk…</div>;
  }
  return <Shell user={me.data}>{children}</Shell>;
}
