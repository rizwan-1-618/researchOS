"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { Button, Empty, ErrorText, Field, control, useRefresh } from "@/components/ui";
import { api } from "@/lib/api";
import type { Collection, Project } from "@/lib/types";

export default function CollectionsPage() {
  const refresh = useRefresh();
  const collections = useQuery({ queryKey: ["collections"], queryFn: () => api<Collection[]>("/api/collections") });
  const projects = useQuery({ queryKey: ["projects"], queryFn: () => api<Project[]>("/api/projects") });
  const [error, setError] = useState<unknown>(null);

  return (
    <div className="space-y-6">
      <h1 className="text-[2rem] font-medium tracking-tight">Collections</h1>
      <form
        className="grid gap-3 rounded-[1.75rem] border border-black/[0.06] bg-white p-4 md:grid-cols-3"
        onSubmit={async (event) => {
          event.preventDefault();
          const form = new FormData(event.currentTarget);
          setError(null);
          try {
            await api("/api/collections", {
              method: "POST",
              body: JSON.stringify({
                name: form.get("name"),
                description: form.get("description") || null,
                project_id: form.get("project_id") || null,
              }),
            });
            event.currentTarget.reset();
            refresh();
          } catch (caught) {
            setError(caught);
          }
        }}
      >
        <Field label="Name">
          <input className={control} name="name" required />
        </Field>
        <Field label="Description">
          <input className={control} name="description" />
        </Field>
        <Field label="Project">
          <select className={control} name="project_id" defaultValue="">
            <option value="">None</option>
            {(projects.data ?? []).map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </Field>
        <Button type="submit">Create collection</Button>
        <ErrorText error={error} />
      </form>
      {collections.data?.length === 0 && <Empty title="No collections" body="Group papers without locking them to one project." />}
      <div className="grid gap-4 md:grid-cols-2">
        {collections.data?.map((collection) => (
          <Link key={collection.id} href={`/app/collections/${collection.id}`} className="rounded-[1.75rem] border border-black/[0.06] bg-white p-5">
            <h2 className="text-lg font-medium tracking-tight">{collection.name}</h2>
            <p className="mt-2 text-sm text-soft">{collection.description}</p>
            <p className="mt-4 text-sm">{collection.paper_count} papers</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
