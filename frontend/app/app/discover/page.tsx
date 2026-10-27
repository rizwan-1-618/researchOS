"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { api } from "@/lib/api";
import type { Discovered, DiscoveryOut, Meta } from "@/lib/types";
import { Button, ErrorText, control, label, useRefresh } from "@/components/ui";

function Discover() {
  const params = useSearchParams();
  const refresh = useRefresh();
  const meta = useQuery({ queryKey: ["meta"], queryFn: () => api<Meta>("/api/meta") });
  const [query, setQuery] = useState(params.get("q") ?? "");
  const [source, setSource] = useState("all");
  const [author, setAuthor] = useState("");
  const [yearFrom, setYearFrom] = useState("");
  const [yearTo, setYearTo] = useState("");
  const [useProfile, setUseProfile] = useState(false);
  const [submitted, setSubmitted] = useState(params.get("q") ?? "");
  const search = useQuery({
    queryKey: ["discover", submitted, source, author, yearFrom, yearTo, useProfile],
    queryFn: () => {
      const searchParams = new URLSearchParams({ q: submitted, source, use_profile: String(useProfile) });
      if (author) searchParams.set("author", author);
      if (yearFrom) searchParams.set("year_from", yearFrom);
      if (yearTo) searchParams.set("year_to", yearTo);
      return api<DiscoveryOut>(`/api/discover?${searchParams}`);
    },
    enabled: submitted.length > 0,
  });
  const save = useMutation({
    mutationFn: (paper: Discovered) =>
      api(`/api/discover/import`, {
        method: "POST",
        body: JSON.stringify({ source: paper.source, external_id: paper.external_id }),
      }),
    onSuccess: () => refresh(),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-[2rem] font-medium tracking-tight">Find the literature</h1>
      </div>
      <form
        className="grid gap-3 rounded-[1.75rem] border border-black/[0.06] bg-white p-4 md:grid-cols-6"
        onSubmit={(event) => {
          event.preventDefault();
          setSubmitted(query.trim());
        }}
      >
        <input className={`${control} md:col-span-2`} value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Quantum machine learning" />
        <select className={control} value={source} onChange={(event) => setSource(event.target.value)}>
          {(meta.data?.discovery_sources ?? ["all"]).map((item) => (
            <option key={item} value={item}>
              {label(item)}
            </option>
          ))}
        </select>
        <input className={control} value={author} onChange={(event) => setAuthor(event.target.value)} placeholder="Author" />
        <input className={control} value={yearFrom} onChange={(event) => setYearFrom(event.target.value)} placeholder="From year" />
        <input className={control} value={yearTo} onChange={(event) => setYearTo(event.target.value)} placeholder="To year" />
        <label className="flex items-center gap-2 text-sm md:col-span-4">
          <input type="checkbox" checked={useProfile} onChange={(event) => setUseProfile(event.target.checked)} />
          Include my research interests
        </label>
        <Button type="submit" className="md:col-span-2">
          Search
        </Button>
      </form>
      <ErrorText error={search.error || save.error} />
      <div className="flex flex-wrap gap-3 text-sm text-soft">
        {search.data?.sources.map((item) => (
          <span key={item.source}>
            {label(item.source)}: {item.error ?? `${item.count} results`}
          </span>
        ))}
      </div>
      <div className="grid gap-4">
        {search.data?.items.map((paper) => (
          <article key={`${paper.source}:${paper.external_id}`} className="rounded-[1.75rem] border border-black/[0.06] bg-white p-5">
            <p className="text-xs uppercase tracking-[0.14em] text-mute">
              {label(paper.source)} {paper.year ? `· ${paper.year}` : ""} {paper.publication ? `· ${paper.publication}` : ""}
            </p>
            <h2 className="mt-2 text-lg font-medium tracking-tight">{paper.title}</h2>
            <p className="mt-2 text-sm text-soft">{paper.authors.join(", ")}</p>
            {paper.abstract && <p className="mt-3 line-clamp-4 text-sm leading-6 text-soft">{paper.abstract}</p>}
            <div className="mt-4">
              {paper.library_paper_id ? (
                <Button tone="ghost" onClick={() => location.assign(`/app/papers/${paper.library_paper_id}`)}>
                  In library
                </Button>
              ) : (
                <Button disabled={save.isPending} onClick={() => save.mutate(paper)}>
                  Save
                </Button>
              )}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

export default function DiscoverPage() {
  return (
    <Suspense>
      <Discover />
    </Suspense>
  );
}
