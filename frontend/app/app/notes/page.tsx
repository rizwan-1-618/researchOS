"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { Button, ErrorText, control, useRefresh } from "@/components/ui";
import { api } from "@/lib/api";
import type { Note, Page } from "@/lib/types";

export default function NotesPage() {
  const refresh = useRefresh();
  const [q, setQ] = useState("");
  const [submitted, setSubmitted] = useState("");
  const notes = useQuery({
    queryKey: ["notes", submitted],
    queryFn: () => api<Page<Note>>(`/api/notes${submitted ? `?q=${encodeURIComponent(submitted)}` : ""}`),
  });
  const [content, setContent] = useState("");
  const [error, setError] = useState<unknown>(null);
  return (
    <div className="space-y-6">
      <h1 className="text-[2rem] font-medium tracking-tight">Notes</h1>
      <form className="space-y-3 rounded-[1.75rem] border border-black/[0.06] bg-white p-4" onSubmit={async (event) => {
        event.preventDefault();
        try {
          await api("/api/notes", { method: "POST", body: JSON.stringify({ content }) });
          setContent("");
          refresh();
        } catch (caught) { setError(caught); }
      }}>
        <textarea className={`${control} min-h-32`} value={content} onChange={(event) => setContent(event.target.value)} placeholder="A note that is not tied to a paper yet" />
        <Button type="submit">Save note</Button>
        <ErrorText error={error} />
      </form>
      <form onSubmit={(event) => { event.preventDefault(); setSubmitted(q.trim()); }}>
        <input className={control} value={q} onChange={(event) => setQ(event.target.value)} placeholder="Search notes" />
      </form>
      {notes.data?.items.map((note) => (
        <article key={note.id} className="rounded-[1.75rem] border border-black/[0.06] bg-white p-5">
          {note.paper_id && <Link className="text-sm font-medium" href={`/app/papers/${note.paper_id}`}>{note.paper_title}</Link>}
          <div className="prose mt-2 max-w-none text-sm leading-6"><ReactMarkdown>{note.content}</ReactMarkdown></div>
        </article>
      ))}
    </div>
  );
}
