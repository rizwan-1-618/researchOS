"use client";

import dynamic from "next/dynamic";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { control, label } from "@/components/ui";
import { api } from "@/lib/api";
import type { GraphPayload, Project } from "@/lib/types";

const GraphView = dynamic(() => import("@/components/graph-view"), { ssr: false });

export default function GraphPage() {
  const router = useRouter();
  const projects = useQuery({ queryKey: ["projects"], queryFn: () => api<Project[]>("/api/projects") });
  const [scope, setScope] = useState("library");
  const [focus, setFocus] = useState("");
  const graph = useQuery({
    queryKey: ["graph", scope, focus],
    queryFn: () => api<GraphPayload>(`/api/graph?scope=${scope}${focus ? `&focus=${focus}` : ""}`),
    enabled: scope !== "project" || focus.length > 0,
  });
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-[2rem] font-medium tracking-tight">Knowledge graph</h1>
        <div className="flex gap-2">
          <select className={control} value={scope} onChange={(event) => { setScope(event.target.value); setFocus(""); }}>
            <option value="library">Library</option>
            <option value="authors">Authors</option>
            <option value="project">Project</option>
          </select>
          {scope === "project" && (
            <select className={control} value={focus} onChange={(event) => setFocus(event.target.value)}>
              <option value="">Choose</option>
              {(projects.data ?? []).map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
            </select>
          )}
        </div>
      </div>
      <div className="grid gap-4 lg:grid-cols-[1fr_260px]">
        <div className="h-[70vh] overflow-hidden rounded-[2rem] bg-sidebar">
          {graph.data && <GraphView graph={graph.data} onOpen={(id) => {
            const [type, value] = id.split(":");
            if (type === "paper") router.push(`/app/papers/${value}`);
            if (type === "author") router.push(`/app/authors/${value}`);
            if (type === "project") router.push(`/app/projects/${value}`);
            if (type === "question") router.push(`/app/questions/${value}`);
          }} />}
        </div>
        <aside className="space-y-3">
          <h2 className="text-base font-medium">Influential papers</h2>
          {graph.data?.influential.map((item) => (
            <button key={item.id} className="block text-left text-sm" type="button" onClick={() => router.push(`/app/papers/${item.id.split(":")[1]}`)}>
              {item.label}
              <span className="mt-1 block text-xs text-mute">PageRank {item.score.toFixed(3)}</span>
            </button>
          ))}
          <p className="text-xs leading-5 text-mute">
            Papers are colored by the community the citation and concept links form. Green arrows are real citations.
            {graph.data ? ` ${graph.data.nodes.length} nodes, ${graph.data.edges.length} links.` : ""}
          </p>
          <ul className="space-y-1 text-xs text-soft">
            <li><span className="mr-2 inline-block h-2 w-2 rounded-full bg-[#7dcea0]" /> Paper community</li>
            <li><span className="mr-2 inline-block h-2 w-2 rounded-full bg-[#85c1e9]" /> Second community</li>
            <li><span className="mr-2 inline-block h-2 w-2 rounded-full bg-[#e7c98a]" /> Shared concept</li>
            <li><span className="mr-2 inline-block h-2 w-2 rounded-full bg-[#9bb8ff]" /> Project</li>
            <li><span className="mr-2 inline-block h-2 w-2 rounded-full bg-[#e7b2a4]" /> Question</li>
          </ul>
          <p className="text-xs text-mute">Open Authors for the collaborator map. {label("library")} is the literature map.</p>
        </aside>
      </div>
    </div>
  );
}
