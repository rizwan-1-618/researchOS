"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { PaperCard } from "@/components/cards";
import { api } from "@/lib/api";
import type { Collection, Page, Paper } from "@/lib/types";

export default function CollectionDetailPage() {
  const params = useParams<{ id: string }>();
  const collections = useQuery({ queryKey: ["collections"], queryFn: () => api<Collection[]>("/api/collections") });
  const papers = useQuery({
    queryKey: ["library", "collection", params.id],
    queryFn: () => api<Page<Paper>>(`/api/papers?collection_id=${params.id}`),
  });
  const collection = collections.data?.find((item) => item.id === params.id);
  return (
    <div className="space-y-6">
      <h1 className="text-[2rem] font-medium tracking-tight">{collection?.name ?? "Collection"}</h1>
      <p className="text-soft">{collection?.description}</p>
      <div className="grid gap-4">
        {papers.data?.items.map((paper) => (
          <PaperCard key={paper.id} paper={paper} />
        ))}
      </div>
    </div>
  );
}
