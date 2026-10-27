"use client";

import Link from "next/link";
import { QueryClient, QueryClientProvider, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

const client = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false, retry: 1 } },
});

export function Providers({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

export function useRefresh() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries();
}

export function label(value: string | null | undefined) {
  if (!value) return "";
  return value.replaceAll("_", " ");
}

export function Button({
  children,
  tone = "pine",
  type = "button",
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { tone?: "pine" | "ink" | "ghost" | "clay" }) {
  const tones = {
    pine: "bg-[#17171a] text-white hover:bg-black",
    ink: "bg-[#17171a] text-white hover:bg-black",
    ghost: "border border-black/[0.08] bg-white text-ink hover:bg-neutral-50",
    clay: "bg-clay text-white hover:opacity-90",
  };
  return (
    <button
      type={type}
      className={`inline-flex items-center justify-center rounded-full px-4 py-2 text-sm disabled:opacity-50 ${tones[tone]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}

export function Field({
  label: text,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block space-y-1.5 text-sm">
      <span className="text-neutral-500">{text}</span>
      {children}
    </label>
  );
}

export const control =
  "w-full rounded-xl border border-black/[0.08] bg-white px-3 py-2 text-ink outline-none focus:border-[#17171a]";

export function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: React.ReactNode;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-40 grid place-items-center bg-ink/40 p-4" onClick={onClose}>
      <div
        className="max-h-[90vh] w-full max-w-lg overflow-auto rounded-[1.75rem] border border-black/[0.06] bg-white p-6 shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between gap-4">
          <h2 className="text-lg font-medium tracking-tight">{title}</h2>
          <button className="text-mute" onClick={onClose} type="button">
            Close
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Empty({ title, body, href, action }: { title: string; body: string; href?: string; action?: string }) {
  return (
    <div className="rounded-[1.75rem] border border-dashed border-neutral-300 bg-white px-6 py-12 text-center">
      <h3 className="text-lg font-medium tracking-tight">{title}</h3>
      <p className="mx-auto mt-2 max-w-md text-neutral-500">{body}</p>
      {href && action && (
        <Link href={href} className="mt-5 inline-flex rounded-full bg-[#17171a] px-4 py-2 text-sm text-white">
          {action}
        </Link>
      )}
    </div>
  );
}

export function ErrorText({ error }: { error: unknown }) {
  if (!error) return null;
  return <p className="text-sm text-clay">{error instanceof Error ? error.message : "Something went wrong"}</p>;
}

export function useToggle(initial = false) {
  const [open, setOpen] = useState(initial);
  return { open, setOpen, toggle: () => setOpen((value) => !value) };
}
