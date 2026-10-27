"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useState } from "react";
import { Button, ErrorText, control, label, useRefresh } from "@/components/ui";
import { api } from "@/lib/api";
import type { Note, Page, Paper, Question } from "@/lib/types";

export default function QuestionDetailPage() {
  const params = useParams<{ id: string }>();
  const refresh = useRefresh();
  const questions = useQuery({ queryKey: ["questions"], queryFn: () => api<Question[]>("/api/questions") });
  const notes = useQuery({ queryKey: ["notes", "question", params.id], queryFn: () => api<Page<Note>>(`/api/notes?question_id=${params.id}`) });
  const [error, setError] = useState<unknown>(null);
  const question = questions.data?.find((item) => item.id === params.id);
  const papers = useQuery({
    queryKey: ["question-papers", question?.paper_ids],
    enabled: Boolean(question),
    queryFn: async () => {
      const rows = await Promise.all((question?.paper_ids ?? []).map((id) => api<Paper>(`/api/papers/${id}`)));
      return rows;
    },
  });

  if (!question) return <p className="text-soft">Loading question…</p>;
  return (
    <div className="space-y-6">
      <p className="text-xs uppercase tracking-[0.18em] text-mute">{label(question.status)}</p>
      <h1 className="text-[2rem] font-medium tracking-tight">{question.title}</h1>
      <p className="max-w-2xl text-soft">{question.description}</p>
      <ErrorText error={error} />
      <div className="flex flex-wrap gap-2">
        {question.allowed_statuses.map((status) => (
          <Button key={status} tone="ghost" onClick={async () => {
            try {
              await api(`/api/questions/${question.id}`, { method: "PATCH", body: JSON.stringify({ status }) });
              refresh();
            } catch (caught) { setError(caught); }
          }}>{label(status)}</Button>
        ))}
      </div>
      <section>
        <h2 className="text-lg font-medium tracking-tight">Evidence</h2>
        {papers.data?.map((paper) => <p key={paper.id} className="mt-2"><a href={`/app/papers/${paper.id}`}>{paper.title}</a></p>)}
        {notes.data?.items.map((note) => <article key={note.id} className="mt-3 rounded-2xl bg-neutral-50 p-4 text-sm">{note.content}</article>)}
      </section>
    </div>
  );
}
