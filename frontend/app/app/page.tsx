"use client";

import { Cabinet, Terminal } from "@lucasmarkes/hairline/react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ProjectPie } from "@/components/project-pie";
import { api } from "@/lib/api";
import type { Overview, Page, Paper, User } from "@/lib/types";

const plate = { "--hairline-plate": "#f3efe6" } as React.CSSProperties;

export default function DashboardPage() {
  const me = useQuery({ queryKey: ["me"], queryFn: () => api<User>("/api/auth/me") });
  const overview = useQuery({ queryKey: ["overview"], queryFn: () => api<Overview>("/api/analytics/overview") });
  const reading = useQuery({
    queryKey: ["library", "reading"],
    queryFn: () => api<Page<Paper>>("/api/papers?status=reading&limit=2"),
  });
  const stats = overview.data;
  const saved = stats?.papers_saved ?? 0;
  const completion = saved === 0 ? 0 : Math.round(((stats?.papers_completed ?? 0) / saved) * 100);
  const projects = stats?.project_progress.slice(0, 3) ?? [];
  const opened = (stats?.weekly_reading ?? []).reduce((sum, point) => sum + point.count, 0);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4 pb-1">
        <h1 className="text-[2rem] leading-none font-medium tracking-tight">
          {me.isPending ? <Bone className="h-9 w-64" /> : `Hi, ${me.data?.name ?? "there"}`}
        </h1>
        <Link href="/app/discover" className="rounded-full bg-[#17171a] px-4 py-2.5 text-sm text-white">
          Discover
        </Link>
      </div>

      <section className="grid items-stretch gap-4 lg:grid-cols-12">
        <article className="flex min-h-[22rem] flex-col rounded-[1.75rem] bg-[#17171a] p-6 text-white lg:col-span-5">
          <p className="text-sm text-white/70">Overall</p>
          <div className="mt-6 grid flex-1 grid-cols-2 content-center gap-6" aria-busy={overview.isPending}>
            <Metric value={stats?.papers_saved} caption="Saved" pending={overview.isPending} />
            <Metric value={stats?.papers_reading} caption="Reading" pending={overview.isPending} />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <Pill value={stats?.projects} caption="Projects" pending={overview.isPending} />
            <Pill value={stats?.tasks_open} caption="Open tasks" pending={overview.isPending} />
            <Pill value={stats?.papers_completed} caption="Completed" pending={overview.isPending} />
          </div>
        </article>

        <article className="flex min-h-[22rem] flex-col rounded-[1.75rem] border border-black/[0.06] bg-white p-6 lg:col-span-4">
          <p className="text-sm font-medium">Weekly reading</p>
          {overview.isPending ? (
            <Bone className="mt-4 h-10 w-16" />
          ) : (
            <p className="mt-4 text-4xl font-medium tabular-nums tracking-tight">{opened}</p>
          )}
          <p className="mt-1 text-xs text-neutral-500">Opened</p>
          <div className="mt-auto h-36" aria-busy={overview.isPending}>
            {overview.isPending ? (
              <Bone className="h-full w-full" />
            ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={stats?.weekly_reading ?? []} margin={{ top: 12, right: 8, left: 0, bottom: 0 }}>
                <XAxis
                  dataKey="week"
                  tickLine={false}
                  axisLine={false}
                  tick={{ fontSize: 11, fill: "#8a8175" }}
                  tickFormatter={(week: string) => week.slice(5)}
                />
                <YAxis hide allowDecimals={false} />
                <Tooltip
                  cursor={{ stroke: "#e0d6c8" }}
                  contentStyle={{ borderRadius: 12, borderColor: "#e0d6c8", fontSize: 12 }}
                />
                <Line type="monotone" dataKey="count" stroke="#17171a" strokeWidth={1.75} dot={false} />
              </LineChart>
            </ResponsiveContainer>
            )}
          </div>
        </article>

        <article className="flex min-h-[22rem] flex-col rounded-[1.75rem] border border-black/[0.06] bg-white p-6 lg:col-span-3">
          <p className="text-sm font-medium">Completed</p>
          <p className="mt-1 text-xs text-neutral-500">Of the papers saved</p>
          <div className="grid flex-1 place-items-center" aria-busy={overview.isPending}>
            {overview.isPending ? <Bone className="size-36 rounded-full!" /> : <Ring value={completion} />}
          </div>
          {overview.isPending ? (
            <Bone className="mx-auto h-4 w-24" />
          ) : (
            <p className="text-center text-sm text-neutral-500">
              {stats?.papers_completed ?? "—"} of {stats?.papers_saved ?? "—"}
            </p>
          )}
        </article>
      </section>

      <section className="grid items-center gap-4 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.2fr)]">
        {overview.isPending ? (
          <Bone className="aspect-[5/4] w-full rounded-[1.75rem]" />
        ) : (
          <Link href="/app/projects" aria-label="Projects">
            <Cabinet label="A rack of blades" theme="light" className="w-full" style={plate} />
          </Link>
        )}
        <div className="grid gap-4 sm:grid-cols-2" aria-busy={overview.isPending}>
          {overview.isPending ? (
            <>
              <ProjectSkeleton />
              <ProjectSkeleton />
            </>
          ) : projects.length ? (
            projects.map((project) => {
              const percent = Math.round(project.progress * 100);
              return (
                <Link
                  key={project.id}
                  href={`/app/projects/${project.id}`}
                  className="flex min-h-52 flex-col items-center justify-between rounded-[1.5rem] bg-[#17171a] px-5 py-5 text-white"
                >
                  <p className="w-full text-base font-medium">{project.name}</p>
                  <ProjectPie percent={percent} />
                  <p className="text-xs text-white/60">
                    {project.papers} papers · {project.notes} notes
                  </p>
                </Link>
              );
            })
          ) : (
            <Link
              href="/app/projects"
              className="grid min-h-52 place-items-center rounded-[1.5rem] border border-dashed border-neutral-300 text-sm text-neutral-500"
            >
              Open a project
            </Link>
          )}
        </div>
      </section>

      <section className="grid items-center gap-4 lg:grid-cols-2">
        <div>
          <div className="mb-3 flex items-baseline justify-between">
            <p className="text-sm font-medium">Continue reading</p>
            <Link href="/app/library" className="text-sm text-neutral-500">
              Library
            </Link>
          </div>
          <div className="grid gap-4" aria-busy={reading.isPending}>
            {reading.isPending ? (
              <>
                <ReadingSkeleton />
                <ReadingSkeleton />
              </>
            ) : reading.data?.items.length ? (
              reading.data.items.map((paper) => (
                <Link
                  key={paper.id}
                  href={`/app/papers/${paper.id}`}
                  className="flex min-h-28 flex-col justify-between rounded-[1.5rem] border border-black/[0.06] bg-white p-4"
                >
                  <p className="text-sm leading-5 font-medium">{paper.title}</p>
                  <p className="text-xs text-neutral-500">{paper.year ?? "Undated"}</p>
                </Link>
              ))
            ) : (
              <p className="text-sm text-neutral-500">Nothing is marked as reading.</p>
            )}
          </div>
        </div>
        {reading.isPending ? (
          <Bone className="aspect-[5/4] w-full rounded-[1.75rem]" />
        ) : (
          <Link href="/app/library" aria-label="Library">
            <Terminal label="A terminal window" theme="light" className="w-full" style={plate} />
          </Link>
        )}
      </section>
    </div>
  );
}

function Bone({ className, tone = "light" }: { className: string; tone?: "light" | "dark" }) {
  const fill = tone === "dark" ? "bg-white/15" : "bg-neutral-200";
  return <span aria-hidden className={`block animate-pulse rounded-lg ${fill} ${className}`} />;
}

function Metric({ value, caption, pending }: { value: number | undefined; caption: string; pending: boolean }) {
  return (
    <div>
      {pending ? <Bone tone="dark" className="h-12 w-16" /> : <p className="text-5xl font-medium tabular-nums tracking-tight">{value ?? "—"}</p>}
      <p className="mt-1 text-sm text-white/60">{caption}</p>
    </div>
  );
}

function Pill({ value, caption, pending }: { value: number | undefined; caption: string; pending: boolean }) {
  return (
    <div className="rounded-2xl bg-white/10 px-3 py-4">
      {pending ? <Bone tone="dark" className="h-8 w-10" /> : <p className="text-2xl font-medium tabular-nums">{value ?? "—"}</p>}
      <p className="mt-1 text-xs text-white/60">{caption}</p>
    </div>
  );
}

function ProjectSkeleton() {
  return (
    <div className="flex min-h-52 flex-col items-center justify-between rounded-[1.5rem] bg-[#17171a] px-5 py-5">
      <Bone tone="dark" className="h-5 w-32 self-start" />
      <Bone tone="dark" className="size-32 rounded-full!" />
      <Bone tone="dark" className="h-3 w-28" />
    </div>
  );
}

function ReadingSkeleton() {
  return (
    <div className="flex min-h-28 flex-col justify-between rounded-[1.5rem] border border-black/[0.06] bg-white p-4">
      <Bone className="h-4 w-4/5" />
      <Bone className="h-3 w-12" />
    </div>
  );
}

function Ring({ value }: { value: number }) {
  return (
    <div
      className="grid size-36 place-items-center rounded-full"
      style={{ background: `conic-gradient(#17171a ${value * 3.6}deg, #eceae6 0deg)` }}
    >
      <div className="grid size-[6.75rem] place-items-center rounded-full bg-white text-xl font-medium tabular-nums">
        {value}%
      </div>
    </div>
  );
}
