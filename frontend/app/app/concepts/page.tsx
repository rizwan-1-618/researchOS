"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Button, ErrorText, Field, control, label, useRefresh } from "@/components/ui";
import { api } from "@/lib/api";
import type { Concept } from "@/lib/types";

export default function ConceptsPage() {
  const refresh = useRefresh();
  const concepts = useQuery({ queryKey: ["concepts"], queryFn: () => api<Concept[]>("/api/concepts") });
  const [error, setError] = useState<unknown>(null);
  return (
    <div className="space-y-6">
      <h1 className="text-[2rem] font-medium tracking-tight">Concepts</h1>
      <form className="grid gap-3 rounded-[1.75rem] border border-black/[0.06] bg-white p-4 md:grid-cols-2" onSubmit={async (event) => {
        event.preventDefault();
        const form = new FormData(event.currentTarget);
        try {
          await api("/api/concepts", { method: "POST", body: JSON.stringify({ name: form.get("name"), description: form.get("description") || null }) });
          event.currentTarget.reset();
          refresh();
        } catch (caught) { setError(caught); }
      }}>
        <Field label="Name"><input className={control} name="name" required /></Field>
        <Field label="Description"><input className={control} name="description" /></Field>
        <Button type="submit">Add concept</Button>
        <ErrorText error={error} />
      </form>
      <div className="grid gap-3 md:grid-cols-2">
        {concepts.data?.map((concept) => (
          <article key={concept.id} className="rounded-[1.75rem] border border-black/[0.06] bg-white p-5">
            <h2 className="text-lg font-medium tracking-tight">{concept.name}</h2>
            <p className="mt-2 text-sm text-soft">{concept.description}</p>
            <p className="mt-3 text-xs uppercase tracking-[0.14em] text-mute">{label(concept.source)} · {concept.paper_count} papers</p>
          </article>
        ))}
      </div>
    </div>
  );
}
