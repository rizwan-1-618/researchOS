"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { ProjectPie } from "@/components/project-pie";
import { Button, Empty, ErrorText, Field, control, label, useRefresh } from "@/components/ui";
import { api } from "@/lib/api";
import type { Meta, Project } from "@/lib/types";

export default function ProjectsPage() {
  const refresh = useRefresh();
  const projects = useQuery({ queryKey: ["projects"], queryFn: () => api<Project[]>("/api/projects") });
  const meta = useQuery({ queryKey: ["meta"], queryFn: () => api<Meta>("/api/meta") });
  const [error, setError] = useState<unknown>(null);
  return (
    <div className="space-y-6">
      <h1 className="text-[2rem] font-medium tracking-tight">Projects</h1>
      <form
        className="grid gap-3 rounded-[1.75rem] border border-black/[0.06] bg-white p-4 md:grid-cols-3"
        onSubmit={async (event) => {
          event.preventDefault();
          const form = new FormData(event.currentTarget);
          try {
            await api("/api/projects", {
              method: "POST",
              body: JSON.stringify({ name: form.get("name"), description: form.get("description") || null, status: form.get("status") }),
            });
            event.currentTarget.reset();
            refresh();
          } catch (caught) {
            setError(caught);
          }
        }}
      >
        <Field label="Name"><input className={control} name="name" required /></Field>
        <Field label="Description"><input className={control} name="description" /></Field>
        <Field label="Status">
          <select className={control} name="status" defaultValue="active">
            {(meta.data?.project_statuses ?? ["active"]).map((status) => (
              <option key={status} value={status}>{label(status)}</option>
            ))}
          </select>
        </Field>
        <Button type="submit">Create project</Button>
        <ErrorText error={error} />
      </form>
      {projects.data?.length === 0 && <Empty title="No projects yet" body="A project holds the papers, questions, and tasks of one investigation." />}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {projects.data?.map((project) => (
          <Link
            key={project.id}
            href={`/app/projects/${project.id}`}
            className="flex min-h-52 flex-col items-center justify-between rounded-[1.5rem] bg-[#17171a] px-5 py-5 text-white"
          >
            <div className="w-full">
              <h2 className="text-base font-medium">{project.name}</h2>
              {project.description && <p className="mt-1 line-clamp-2 text-xs text-white/60">{project.description}</p>}
            </div>
            <ProjectPie percent={Math.round(project.progress * 100)} />
            <p className="text-xs text-white/60">
              {project.paper_count} papers · {project.note_count} notes
            </p>
          </Link>
        ))}
      </div>
    </div>
  );
}
