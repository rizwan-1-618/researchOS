"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { Button, ErrorText, Field, control, label, useRefresh } from "@/components/ui";
import { api } from "@/lib/api";
import type { Meta, Project, Question } from "@/lib/types";

export default function QuestionsPage() {
  const refresh = useRefresh();
  const questions = useQuery({ queryKey: ["questions"], queryFn: () => api<Question[]>("/api/questions") });
  const projects = useQuery({ queryKey: ["projects"], queryFn: () => api<Project[]>("/api/projects") });
  const meta = useQuery({ queryKey: ["meta"], queryFn: () => api<Meta>("/api/meta") });
  const [error, setError] = useState<unknown>(null);
  return (
    <div className="space-y-6">
      <h1 className="text-[2rem] font-medium tracking-tight">Research questions</h1>
      <form className="grid max-w-xl gap-3 rounded-[1.75rem] border border-black/[0.06] bg-white p-4" onSubmit={async (event) => {
        event.preventDefault();
        const form = new FormData(event.currentTarget);
        try {
          await api("/api/questions", { method: "POST", body: JSON.stringify({ title: form.get("title"), description: form.get("description") || null, project_id: form.get("project_id") || null, status: "draft" }) });
          event.currentTarget.reset();
          refresh();
        } catch (caught) { setError(caught); }
      }}>
        <Field label="Question"><input className={control} name="title" required /></Field>
        <Field label="Description"><textarea className={control} name="description" /></Field>
        <Field label="Project">
          <select className={control} name="project_id" defaultValue="">
            <option value="">None</option>
            {(projects.data ?? []).map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
          </select>
        </Field>
        <Button type="submit">Create question</Button>
        <ErrorText error={error} />
      </form>
      <div className="grid gap-3">
        {questions.data?.map((question) => (
          <Link key={question.id} href={`/app/questions/${question.id}`} className="rounded-[1.75rem] border border-black/[0.06] bg-white p-5">
            <p className="text-xs uppercase tracking-[0.14em] text-mute">{label(question.status)}</p>
            <h2 className="mt-2 text-lg font-medium tracking-tight">{question.title}</h2>
            <p className="mt-2 text-sm text-soft">{question.paper_ids.length} papers · {question.note_count} notes</p>
          </Link>
        ))}
      </div>
      <p className="text-xs text-mute">Statuses follow {meta.data ? "the research question workflow." : ""}</p>
    </div>
  );
}
