"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import { api } from "@/lib/api";
import type { Concept, Highlight, Question } from "@/lib/types";
import { Button, control, useRefresh } from "@/components/ui";

pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";

export default function Reader({ paperId }: { paperId: string }) {
  const refresh = useRefresh();
  const pageRef = useRef<HTMLDivElement>(null);
  const [pages, setPages] = useState(0);
  const [page, setPage] = useState(1);
  const [outline, setOutline] = useState<{ title: string; page: number }[]>([]);
  const [draft, setDraft] = useState<{ text: string; rects: Highlight["rects"] } | null>(null);
  const [comment, setComment] = useState("");
  const [conceptId, setConceptId] = useState("");
  const [questionId, setQuestionId] = useState("");
  const highlights = useQuery({
    queryKey: ["highlights", paperId],
    queryFn: () => api<Highlight[]>(`/api/highlights?paper_id=${paperId}`),
  });
  const concepts = useQuery({ queryKey: ["concepts"], queryFn: () => api<Concept[]>("/api/concepts") });
  const questions = useQuery({ queryKey: ["questions"], queryFn: () => api<Question[]>("/api/questions") });
  const save = useMutation({
    mutationFn: () =>
      api("/api/highlights", {
        method: "POST",
        body: JSON.stringify({
          paper_id: paperId,
          page,
          selected_text: draft?.text,
          comment: comment || null,
          rects: draft?.rects ?? [],
          concept_ids: conceptId ? [conceptId] : [],
          question_ids: questionId ? [questionId] : [],
        }),
      }),
    onSuccess: () => {
      setDraft(null);
      setComment("");
      refresh();
    },
  });

  useEffect(() => {
    api(`/api/papers/${paperId}/opened`, { method: "POST" }).catch(() => undefined);
    api<{ status: string | null }>(`/api/papers/${paperId}`)
      .then((paper) => {
        if (paper.status === "to_read") {
          return api(`/api/papers/${paperId}/library`, {
            method: "PATCH",
            body: JSON.stringify({ status: "reading" }),
          });
        }
      })
      .catch(() => undefined);
  }, [paperId]);

  function capture() {
    const selection = window.getSelection();
    const root = pageRef.current;
    if (!selection || selection.isCollapsed || !root || !selection.anchorNode || !root.contains(selection.anchorNode)) return;
    const range = selection.getRangeAt(0);
    const bounds = root.getBoundingClientRect();
    const rects = Array.from(range.getClientRects()).map((rect) => ({
      x: (rect.left - bounds.left) / bounds.width,
      y: (rect.top - bounds.top) / bounds.height,
      width: rect.width / bounds.width,
      height: rect.height / bounds.height,
    }));
    const text = selection.toString().trim();
    if (text) setDraft({ text, rects });
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[180px_1fr_280px]">
      <aside className="space-y-2 text-sm">
        <p className="text-xs uppercase tracking-[0.14em] text-mute">Pages</p>
        {Array.from({ length: pages }, (_, index) => (
          <button key={index} className={`block ${page === index + 1 ? "text-pine" : ""}`} type="button" onClick={() => setPage(index + 1)}>
            {index + 1}
          </button>
        ))}
        {outline.length > 0 && <p className="pt-4 text-xs uppercase tracking-[0.14em] text-mute">Outline</p>}
        {outline.map((item) => (
          <button key={`${item.title}-${item.page}`} className="block text-left" type="button" onClick={() => setPage(item.page)}>
            {item.title}
          </button>
        ))}
      </aside>
      <div className="overflow-auto rounded-3xl bg-white p-4" onMouseUp={capture}>
        <Document
          file={`/api/papers/${paperId}/file`}
          onLoadSuccess={async (document) => {
            setPages(document.numPages);
            const entries = (await document.getOutline()) ?? [];
            const mapped = [];
            for (const entry of entries) {
              if (!entry.dest) continue;
              const destination = typeof entry.dest === "string" ? await document.getDestination(entry.dest) : entry.dest;
              if (!destination) continue;
              const index = await document.getPageIndex(destination[0]);
              mapped.push({ title: entry.title, page: index + 1 });
            }
            setOutline(mapped);
          }}
        >
          <div ref={pageRef} className="relative inline-block">
            <Page pageNumber={page} width={720} />
            {(highlights.data ?? [])
              .filter((item) => item.page === page)
              .flatMap((item) =>
                item.rects.map((rect, index) => (
                  <span
                    key={`${item.id}-${index}`}
                    className="absolute bg-gold/30"
                    style={{ left: `${rect.x * 100}%`, top: `${rect.y * 100}%`, width: `${rect.width * 100}%`, height: `${rect.height * 100}%` }}
                  />
                )),
              )}
          </div>
        </Document>
      </div>
      <aside className="space-y-3">
        <h2 className="text-base font-medium">Annotation</h2>
        {draft ? (
          <form
            className="space-y-2 rounded-2xl bg-neutral-50 p-3"
            onSubmit={(event) => {
              event.preventDefault();
              save.mutate();
            }}
          >
            <p className="text-sm">{draft.text}</p>
            <textarea className={control} value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Comment" />
            <select className={control} value={conceptId} onChange={(event) => setConceptId(event.target.value)}>
              <option value="">Concept</option>
              {(concepts.data ?? []).map((concept) => (
                <option key={concept.id} value={concept.id}>
                  {concept.name}
                </option>
              ))}
            </select>
            <select className={control} value={questionId} onChange={(event) => setQuestionId(event.target.value)}>
              <option value="">Question</option>
              {(questions.data ?? []).map((question) => (
                <option key={question.id} value={question.id}>
                  {question.title}
                </option>
              ))}
            </select>
            <Button type="submit" disabled={save.isPending}>
              Save highlight
            </Button>
          </form>
        ) : (
          <p className="text-sm text-soft">Select a passage in the PDF.</p>
        )}
        {(highlights.data ?? []).map((item) => (
          <article key={item.id} className="rounded-2xl border border-black/[0.06] p-3 text-sm">
            <p className="text-xs text-mute">Page {item.page}</p>
            <p>{item.selected_text}</p>
            {item.comment && <p className="mt-1 text-soft">{item.comment}</p>}
          </article>
        ))}
      </aside>
    </div>
  );
}
