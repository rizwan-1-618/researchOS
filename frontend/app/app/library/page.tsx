"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { PaperCard } from "@/components/cards";
import { Empty, control, label, useRefresh } from "@/components/ui";
import { api } from "@/lib/api";
import type { Meta, Page, Paper, Tag } from "@/lib/types";

export default function LibraryPage() {
  const meta = useQuery({ queryKey: ["meta"], queryFn: () => api<Meta>("/api/meta") });
  const tags = useQuery({ queryKey: ["tags"], queryFn: () => api<Tag[]>("/api/tags") });
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [tag, setTag] = useState("");
  const [mode, setMode] = useState("keyword");
  const [submitted, setSubmitted] = useState("");
  const refresh = useRefresh();
  const library = useQuery({
    queryKey: ["library", status, submitted, tag, mode],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (status) params.set("status", status);
      if (tag) params.set("tag_id", tag);
      if (submitted && mode !== "keyword") {
        params.set("q", submitted);
        params.set("mode", mode);
        const result = await api<{ papers: { paper: Paper; snippet: string | null; score: number }[] }>(`/api/search?${params}`);
        return { items: result.papers.map((hit) => hit.paper), total: result.papers.length, limit: result.papers.length, offset: 0 } satisfies Page<Paper>;
      }
      if (submitted) params.set("q", submitted);
      return api<Page<Paper>>(`/api/papers?${params}`);
    },
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-[2rem] font-medium tracking-tight">Your papers</h1>
      </div>
      <label className="inline-flex cursor-pointer rounded-full bg-[#17171a] px-4 py-2 text-sm text-white">
        Upload PDF
        <input
          className="hidden"
          type="file"
          accept="application/pdf"
          onChange={async (event) => {
            const file = event.target.files?.[0];
            if (!file) return;
            const body = new FormData();
            body.set("file", file);
            await api("/api/papers/upload", { method: "POST", body });
            refresh();
          }}
        />
      </label>
      <form
        className="grid gap-3 md:grid-cols-5"
        onSubmit={(event) => {
          event.preventDefault();
          setSubmitted(q.trim());
        }}
      >
        <input className={control} value={q} onChange={(event) => setQ(event.target.value)} placeholder="Search saved papers" />
        <select className={control} value={mode} onChange={(event) => setMode(event.target.value)}>
          {(meta.data?.search_modes ?? ["keyword", "semantic", "hybrid"]).map((item) => (
            <option key={item} value={item}>
              {label(item)}
            </option>
          ))}
        </select>
        <select className={control} value={status} onChange={(event) => setStatus(event.target.value)}>
          <option value="">Any status</option>
          {(meta.data?.reading_statuses ?? []).map((item) => (
            <option key={item} value={item}>
              {label(item)}
            </option>
          ))}
        </select>
        <select className={control} value={tag} onChange={(event) => setTag(event.target.value)}>
          <option value="">Any tag</option>
          {(tags.data ?? []).map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>
        <button className="rounded-full bg-[#17171a] px-4 py-2 text-sm text-white" type="submit">
          Filter
        </button>
      </form>
      {library.data && library.data.items.length === 0 && (
        <Empty title="The shelf is empty" body="Save a paper from Discover or upload a PDF." href="/app/discover" action="Discover papers" />
      )}
      <div className="grid gap-4">
        {library.data?.items.map((paper) => (
          <PaperCard key={paper.id} paper={paper} />
        ))}
      </div>
    </div>
  );
}
