"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Button, ErrorText, Field, control, label, useRefresh } from "@/components/ui";
import { api } from "@/lib/api";
import type { Meta, Project, Task } from "@/lib/types";

export default function TasksPage() {
  const refresh = useRefresh();
  const tasks = useQuery({ queryKey: ["tasks"], queryFn: () => api<Task[]>("/api/tasks") });
  const projects = useQuery({ queryKey: ["projects"], queryFn: () => api<Project[]>("/api/projects") });
  const meta = useQuery({ queryKey: ["meta"], queryFn: () => api<Meta>("/api/meta") });
  const [error, setError] = useState<unknown>(null);

  async function update(id: string, body: Record<string, string>) {
    try {
      await api(`/api/tasks/${id}`, { method: "PATCH", body: JSON.stringify(body) });
      refresh();
    } catch (caught) {
      setError(caught);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-[2rem] font-medium tracking-tight">Tasks</h1>
      <form className="grid gap-3 rounded-[1.75rem] border border-black/[0.06] bg-white p-4 md:grid-cols-3" onSubmit={async (event) => {
        event.preventDefault();
        const form = new FormData(event.currentTarget);
        try {
          await api("/api/tasks", { method: "POST", body: JSON.stringify({ title: form.get("title"), description: form.get("description") || null, project_id: form.get("project_id") || null, priority: form.get("priority"), deadline: form.get("deadline") || null, status: "todo" }) });
          event.currentTarget.reset();
          refresh();
        } catch (caught) { setError(caught); }
      }}>
        <Field label="Title"><input className={control} name="title" required /></Field>
        <Field label="Description"><input className={control} name="description" /></Field>
        <Field label="Deadline"><input className={control} name="deadline" type="date" /></Field>
        <Field label="Project">
          <select className={control} name="project_id" defaultValue=""><option value="">None</option>{(projects.data ?? []).map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select>
        </Field>
        <Field label="Priority">
          <select className={control} name="priority" defaultValue="medium">{(meta.data?.task_priorities ?? ["medium"]).map((priority) => <option key={priority} value={priority}>{label(priority)}</option>)}</select>
        </Field>
        <Button type="submit">Add task</Button>
        <ErrorText error={error} />
      </form>
      <div className="grid gap-3">
        {tasks.data?.map((task) => (
          <article key={task.id} className="flex flex-wrap items-center justify-between gap-3 rounded-[1.75rem] border border-black/[0.06] bg-white p-4">
            <div>
              <h2 className="text-lg">{task.title}</h2>
              <p className="text-sm text-soft">{label(task.priority)} {task.deadline ? `· due ${task.deadline}` : ""}</p>
            </div>
            <select className={`${control} w-40! shrink-0`} value={task.status} onChange={(event) => update(task.id, { status: event.target.value })}>
              {(meta.data?.task_statuses ?? []).map((status) => <option key={status} value={status}>{label(status)}</option>)}
            </select>
          </article>
        ))}
      </div>
    </div>
  );
}
