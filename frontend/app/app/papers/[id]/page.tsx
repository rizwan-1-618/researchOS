"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { Button, ErrorText, Field, control, label, useRefresh } from "@/components/ui";
import { api } from "@/lib/api";
import type { Collection, Concept, Meta, Note, Page, Paper, Project } from "@/lib/types";

export default function PaperPage() {
  const params = useParams<{ id: string }>();
  const refresh = useRefresh();
  const paper = useQuery({ queryKey: ["paper", params.id], queryFn: () => api<Paper>(`/api/papers/${params.id}`) });
  const meta = useQuery({ queryKey: ["meta"], queryFn: () => api<Meta>("/api/meta") });
  const concepts = useQuery({ queryKey: ["concepts"], queryFn: () => api<Concept[]>("/api/concepts") });
  const projects = useQuery({ queryKey: ["projects"], queryFn: () => api<Project[]>("/api/projects") });
  const collections = useQuery({ queryKey: ["collections"], queryFn: () => api<Collection[]>("/api/collections") });
  const notes = useQuery({
    queryKey: ["notes", params.id],
    queryFn: () => api<Page<Note>>(`/api/notes?paper_id=${params.id}`),
  });
  const citations = useQuery({
    queryKey: ["citations", params.id],
    queryFn: () => api<{ references: Paper[]; cited_by: Paper[] }>(`/api/papers/${params.id}/citations`),
  });
  const [tag, setTag] = useState("");
  const [note, setNote] = useState("");
  const [conceptId, setConceptId] = useState("");
  const [relationship, setRelationship] = useState("related_to");
  const [error, setError] = useState<unknown>(null);

  async function run(work: () => Promise<unknown>) {
    setError(null);
    try {
      await work();
      refresh();
    } catch (caught) {
      setError(caught);
    }
  }

  const upload = useMutation({
    mutationFn: async (file: File) => {
      const body = new FormData();
      body.set("file", file);
      return api(`/api/papers/${params.id}/file`, { method: "POST", body });
    },
    onSuccess: () => refresh(),
  });

  if (!paper.data) return <p className="text-soft">Loading the paper…</p>;
  const item = paper.data;

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-mute">
            {item.year} {item.publication ? `· ${item.publication}` : ""} · {label(item.embedding_status)}
          </p>
          <h1 className="mt-2 max-w-4xl text-[2rem] font-medium leading-tight tracking-tight">{item.title}</h1>
          <p className="mt-3 text-soft">
            {item.authors.map((author) => (
              <Link key={author.id} href={`/app/authors/${author.id}`} className="mr-3 underline decoration-line">
                {author.name}
              </Link>
            ))}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {item.has_file && (
            <Link href={`/app/papers/${item.id}/read`} className="rounded-full bg-[#17171a] px-4 py-2 text-sm text-white">
              Read PDF
            </Link>
          )}
          <Button
            tone="ghost"
            onClick={() =>
              run(() =>
                api(`/api/papers/${item.id}/library`, {
                  method: "PATCH",
                  body: JSON.stringify({ is_important: !item.is_important }),
                }),
              )
            }
          >
            {item.is_important ? "Important" : "Mark important"}
          </Button>
          <Button
            tone="ghost"
            onClick={() =>
              run(() =>
                api(`/api/papers/${item.id}/library`, {
                  method: "PATCH",
                  body: JSON.stringify({ is_favorite: !item.is_favorite }),
                }),
              )
            }
          >
            {item.is_favorite ? "Favorite" : "Favorite it"}
          </Button>
        </div>
      </div>
      <ErrorText error={error || upload.error} />
      <div className="grid gap-6 lg:grid-cols-[1.4fr_0.8fr]">
        <div className="space-y-6">
          <p className="text-lg leading-8">{item.abstract || "No abstract yet."}</p>
          <section className="space-y-3">
            <h2 className="text-lg font-medium tracking-tight">Notes</h2>
            <form
              className="space-y-3"
              onSubmit={(event) => {
                event.preventDefault();
                const content = note;
                setNote("");
                run(() => api("/api/notes", { method: "POST", body: JSON.stringify({ content, paper_id: item.id }) }));
              }}
            >
              <textarea className={`${control} min-h-28`} value={note} onChange={(event) => setNote(event.target.value)} placeholder="What matters on this paper?" />
              <Button type="submit">Save note</Button>
            </form>
            {notes.data?.items.map((entry) => (
              <article key={entry.id} className="rounded-2xl bg-neutral-50 p-4 text-sm leading-6">
                {entry.content}
              </article>
            ))}
          </section>
          <section className="grid gap-4 md:grid-cols-2">
            <div>
              <h2 className="text-base font-medium">References</h2>
              {(citations.data?.references ?? []).map((cited) => (
                <Link key={cited.id} href={`/app/papers/${cited.id}`} className="mt-2 block text-sm">
                  {cited.title}
                </Link>
              ))}
            </div>
            <div>
              <h2 className="text-base font-medium">Cited by</h2>
              {(citations.data?.cited_by ?? []).map((cited) => (
                <Link key={cited.id} href={`/app/papers/${cited.id}`} className="mt-2 block text-sm">
                  {cited.title}
                </Link>
              ))}
            </div>
          </section>
        </div>
        <aside className="space-y-5 rounded-[1.75rem] border border-black/[0.06] bg-white p-5">
          <Field label="Reading status">
            <select
              className={control}
              value={item.status ?? "to_read"}
              onChange={(event) =>
                run(() =>
                  api(`/api/papers/${item.id}/library`, {
                    method: "PATCH",
                    body: JSON.stringify({ status: event.target.value }),
                  }),
                )
              }
            >
              {(meta.data?.reading_statuses ?? []).map((status) => (
                <option key={status} value={status}>
                  {label(status)}
                </option>
              ))}
            </select>
          </Field>
          <form
            className="flex gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              const name = tag;
              setTag("");
              run(() => api(`/api/papers/${item.id}/tags`, { method: "POST", body: JSON.stringify({ name }) }));
            }}
          >
            <input className={control} value={tag} onChange={(event) => setTag(event.target.value)} placeholder="Add a tag" />
            <Button type="submit">Add</Button>
          </form>
          <div className="flex flex-wrap gap-2">
            {item.tags.map((entry) => (
              <button
                key={entry.id}
                className="rounded-full bg-neutral-100 px-2 py-1 text-xs"
                type="button"
                onClick={() => run(() => api(`/api/papers/${item.id}/tags/${entry.id}`, { method: "DELETE" }))}
              >
                {entry.name} ×
              </button>
            ))}
          </div>
          <form
            className="space-y-2"
            onSubmit={(event) => {
              event.preventDefault();
              run(() =>
                api(`/api/papers/${item.id}/concepts`, {
                  method: "POST",
                  body: JSON.stringify({ concept_id: conceptId, relationship_type: relationship }),
                }),
              );
            }}
          >
            <Field label="Link a concept">
              <select className={control} value={conceptId} onChange={(event) => setConceptId(event.target.value)}>
                <option value="">Choose</option>
                {(concepts.data ?? []).map((concept) => (
                  <option key={concept.id} value={concept.id}>
                    {concept.name}
                  </option>
                ))}
              </select>
            </Field>
            <select className={control} value={relationship} onChange={(event) => setRelationship(event.target.value)}>
              {(meta.data?.relationship_types ?? []).map((type) => (
                <option key={type} value={type}>
                  {label(type)}
                </option>
              ))}
            </select>
            <Button type="submit" disabled={!conceptId}>
              Link
            </Button>
          </form>
          <ul className="text-sm">
            {(item.concepts ?? []).map((concept) => (
              <li key={`${concept.id}-${concept.relationship_type}`}>
                {concept.name} · {label(concept.relationship_type)}
              </li>
            ))}
          </ul>
          <Field label="Add to project">
            <select
              className={control}
              defaultValue=""
              onChange={(event) => {
                if (event.target.value) {
                  run(() => api(`/api/projects/${event.target.value}/papers`, { method: "POST", body: JSON.stringify({ ids: [item.id] }) }));
                }
              }}
            >
              <option value="">Choose a project</option>
              {(projects.data ?? []).map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Add to collection">
            <select
              className={control}
              defaultValue=""
              onChange={(event) => {
                if (event.target.value) {
                  run(() =>
                    api(`/api/collections/${event.target.value}/papers`, {
                      method: "POST",
                      body: JSON.stringify({ ids: [item.id] }),
                    }),
                  );
                }
              }}
            >
              <option value="">Choose a collection</option>
              {(collections.data ?? []).map((collection) => (
                <option key={collection.id} value={collection.id}>
                  {collection.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="PDF">
            <input
              className="text-sm"
              type="file"
              accept="application/pdf"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) upload.mutate(file);
              }}
            />
          </Field>
          {item.processing_status && <p className="text-sm text-soft">File: {label(item.processing_status)}</p>}
          {item.processing_error && <p className="text-sm text-clay">{item.processing_error}</p>}
          {item.pdf_url && (
            <a className="text-sm underline" href={item.pdf_url} target="_blank" rel="noreferrer">
              Source PDF
            </a>
          )}
          <Button tone="ghost" onClick={() => run(() => api(`/api/papers/${item.id}`, { method: "DELETE" }))}>
            Remove from library
          </Button>
        </aside>
      </div>
    </div>
  );
}
