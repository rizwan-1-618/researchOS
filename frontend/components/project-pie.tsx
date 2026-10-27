"use client";

import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";

export function ProjectPie({ percent }: { percent: number }) {
  const done = Math.min(100, Math.max(0, percent));
  return (
    <div className="relative size-32">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={[{ value: done }, { value: 100 - done }]}
            dataKey="value"
            innerRadius="68%"
            outerRadius="100%"
            startAngle={90}
            endAngle={-270}
            stroke="none"
          >
            <Cell fill="#ffffff" />
            <Cell fill="rgba(255,255,255,0.16)" />
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      <p className="pointer-events-none absolute inset-0 grid place-items-center text-sm font-medium tabular-nums">{done}%</p>
    </div>
  );
}
