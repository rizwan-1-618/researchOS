"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { PaperCard } from "@/components/cards";
import { api } from "@/lib/api";
import type { Author, Paper } from "@/lib/types";

type AuthorProfile = {
  id: string;
  name: string;
  affiliation: string | null;
  papers: Paper[];
  collaborators: Author[];
  concepts: string[];
  paper_count: number;
  external_citation_count: number;
};

export default function AuthorPage() {
  const params = useParams<{ id: string }>();
  const author = useQuery({ queryKey: ["author", params.id], queryFn: () => api<AuthorProfile>(`/api/authors/${params.id}`) });
  if (!author.data) return <p className="text-soft">Loading author…</p>;
  const item = author.data;
  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.18em] text-mute">{item.paper_count} papers · {item.external_citation_count} reported citations</p>
        <h1 className="text-[2rem] font-medium tracking-tight">{item.name}</h1>
        <p className="mt-2 text-soft">{item.affiliation}</p>
      </div>
      <section>
        <h2 className="text-lg font-medium tracking-tight">Collaborators</h2>
        <div className="mt-2 flex flex-wrap gap-3">
          {item.collaborators.map((person) => <Link key={person.id} href={`/app/authors/${person.id}`}>{person.name}</Link>)}
        </div>
      </section>
      <section>
        <h2 className="text-lg font-medium tracking-tight">Concepts</h2>
        <p className="mt-2 text-sm text-soft">{item.concepts.join(" · ")}</p>
      </section>
      <section className="grid gap-4">
        {item.papers.map((paper) => <PaperCard key={paper.id} paper={paper} />)}
      </section>
    </div>
  );
}
