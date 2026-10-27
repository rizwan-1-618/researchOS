import Link from "next/link";
import type { Paper } from "@/lib/types";
import { label } from "@/components/ui";

export function PaperCard({ paper, children }: { paper: Paper; children?: React.ReactNode }) {
  return (
    <article className="rounded-[1.75rem] border border-black/[0.06] bg-white p-5">
      <div className="flex flex-wrap items-center gap-2 text-xs text-neutral-500">
        {paper.year && <span>{paper.year}</span>}
        {paper.publication && <span>{paper.publication}</span>}
        {paper.status && <span className="rounded-full bg-neutral-100 px-2 py-1 capitalize">{label(paper.status)}</span>}
        {paper.is_important && <span className="text-clay">Important</span>}
        {paper.is_favorite && <span className="text-gold">Favorite</span>}
      </div>
      <h3 className="mt-2 text-lg leading-tight font-medium tracking-tight">
        <Link href={`/app/papers/${paper.id}`}>{paper.title}</Link>
      </h3>
      <p className="mt-2 text-sm text-neutral-500">{paper.authors.map((author) => author.name).join(", ") || "Authors not recorded"}</p>
      {paper.abstract && <p className="mt-3 line-clamp-3 text-sm leading-6 text-neutral-600">{paper.abstract}</p>}
      {paper.tags.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {paper.tags.map((tag) => (
            <span key={tag.id} className="rounded-full bg-neutral-100 px-2 py-1 text-xs text-neutral-600">
              {tag.name}
            </span>
          ))}
        </div>
      )}
      {children && <div className="mt-4 flex flex-wrap gap-2">{children}</div>}
    </article>
  );
}
