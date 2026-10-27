"use client";

import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "@/lib/api";
import type { Overview } from "@/lib/types";
import { label } from "@/components/ui";

export default function AnalyticsPage() {
  const overview = useQuery({ queryKey: ["overview"], queryFn: () => api<Overview>("/api/analytics/overview") });
  const data = overview.data;
  if (!data) return <p className="text-soft">Gathering the record…</p>;
  return (
    <div className="space-y-8">
      <h1 className="text-[2rem] font-medium tracking-tight">Analytics</h1>
      <section className="grid gap-3 sm:grid-cols-3">
        <Stat name="Authors encountered" value={data.authors_encountered} />
        <Stat name="Unfinished papers" value={data.unfinished_papers} />
        <Stat name="Reading to note" value={data.reading_to_note_rate == null ? "—" : `${Math.round(data.reading_to_note_rate * 100)}%`} />
      </section>
      <section className="rounded-[1.75rem] border border-black/[0.06] bg-white p-4">
        <h2 className="text-lg font-medium tracking-tight">Monthly activity</h2>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.monthly_activity}>
              <XAxis dataKey="month" />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="papers_saved" fill="#17171a" />
              <Bar dataKey="papers_opened" fill="#8a8175" />
              <Bar dataKey="notes_created" fill="#cfc6ba" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>
      <section className="grid gap-6 md:grid-cols-2">
        <div>
          <h2 className="text-lg font-medium tracking-tight">Question status</h2>
          {Object.entries(data.question_status).map(([status, count]) => (
            <p key={status} className="mt-2 flex justify-between text-sm"><span>{label(status)}</span><span>{count}</span></p>
          ))}
        </div>
        <div>
          <h2 className="text-lg font-medium tracking-tight">Tags</h2>
          {data.top_tags.map((tag) => <p key={tag.name} className="mt-2 text-sm">{tag.name} · {tag.count}</p>)}
        </div>
      </section>
      <section>
        <h2 className="text-lg font-medium tracking-tight">Projects</h2>
        {data.project_progress.map((project) => (
          <div key={project.id} className="mt-3">
            <div className="flex justify-between text-sm"><span>{project.name}</span><span>{Math.round(project.progress * 100)}%</span></div>
            <div className="mt-1 h-1 rounded-full bg-neutral-100"><div className="h-1 rounded-full bg-[#17171a]" style={{ width: `${Math.round(project.progress * 100)}%` }} /></div>
          </div>
        ))}
      </section>
    </div>
  );
}

function Stat({ name, value }: { name: string; value: string | number }) {
  return (
    <div className="rounded-[1.75rem] border border-black/[0.06] bg-white p-4">
      <p className="text-xs uppercase tracking-[0.14em] text-mute">{name}</p>
      <p className="mt-2 text-4xl font-medium tracking-tight tabular-nums">{value}</p>
    </div>
  );
}
