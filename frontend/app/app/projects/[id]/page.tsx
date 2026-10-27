"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { PaperCard } from "@/components/cards";
import { Button, ErrorText, Field, control, label, useRefresh } from "@/components/ui";
import { api } from "@/lib/api";
import type { Meta, Page, Paper, Project, Question, Task } from "@/lib/types";

export default function ProjectDetailPage() {
  const params = useParams<{ id: string }>();
  const refresh = useRefresh();
  const project = useQuery({ queryKey: ["project", params.id], queryFn: () => api<Project>(`/api/projects/${params.id}`) });
  const papers = useQuery({ queryKey: ["library", "project", params.id], queryFn: () => api<Page<Paper>>(`/api/papers?project_id=${params.id}`) });
  const questions = useQuery({ queryKey: ["questions", params.id], queryFn: () => api<Question[]>(`/api/questions?project_id=${params.id}`) });
  const tasks = useQuery({ queryKey: ["tasks", params.id], queryFn: () => api<Task[]>(`/api/tasks?project_id=${params.id}`) });
  const meta = useQuery({ queryKey: ["meta"], queryFn: () => api<Meta>("/api/meta") });
  const [error, setError] = useState<unknown>(null);
  const item = project.data;

  async function create(path: string, body: unknown) {
    setError(null);
    try {
      await api(path, { method: "POST", body: JSON.stringify(body) });
      refresh();
    } catch (caught) {
      setError(caught);
    }
  }

  if (!item) return <p className="text-soft">Loading project…</p>;
  return (
    <div className="space-y-8">
      <div>
        <p className="text-xs uppercase tracking-[0.18em] text-mute">{label(item.status)} · {Math.round(item.progress * 100)}%</p>
        <h1 className="text-[2rem] font-medium tracking-tight">{item.name}</h1>
        <p className="mt-2 max-w-2xl text-soft">{item.description}</p>
      </div>
      <ErrorText error={error} />
      <section className="grid gap-6 lg:grid-cols-2">
        <form className="space-y-3 rounded-[1.75rem] border border-black/[0.06] bg-white p-4" onSubmit={(event) => {
          event.preventDefault();
          const form = new FormData(event.currentTarget);
          create("/api/questions", { title: form.get("title"), project_id: params.id, status: "draft" });
          event.currentTarget.reset();
        }}>
          <h2 className="text-lg font-medium tracking-tight">Question</h2>
          <input className={control} name="title" placeholder="What are you trying to find out?" required />
          <Button type="submit">Add question</Button>
          {questions.data?.map((question) => (
            <Link key={question.id} href={`/app/questions/${question.id}`} className="block text-sm">{question.title} · {label(question.status)}</Link>
          ))}
        </form>
        <form className="space-y-3 rounded-[1.75rem] border border-black/[0.06] bg-white p-4" onSubmit={(event) => {
          event.preventDefault();
          const form = new FormData(event.currentTarget);
          create("/api/tasks", { title: form.get("title"), project_id: params.id, priority: form.get("priority"), status: "todo" });
          event.currentTarget.reset();
        }}>
          <h2 className="text-lg font-medium tracking-tight">Task</h2>
          <input className={control} name="title" placeholder="Next concrete step" required />
          <Field label="Priority">
            <select className={control} name="priority" defaultValue="medium">
              {(meta.data?.task_priorities ?? ["medium"]).map((priority) => <option key={priority} value={priority}>{label(priority)}</option>)}
            </select>
          </Field>
          <Button type="submit">Add task</Button>
          {tasks.data?.map((task) => <p key={task.id} className="text-sm">{task.title} · {label(task.status)}</p>)}
        </form>
      </section>
      <section className="space-y-3">
        <h2 className="text-lg font-medium tracking-tight">Papers</h2>
        {papers.data?.items.map((paper) => <PaperCard key={paper.id} paper={paper} />)}
      </section>
    </div>
  );
}
