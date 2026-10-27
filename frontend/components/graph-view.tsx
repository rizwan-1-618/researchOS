"use client";

import { forceCollide, forceX } from "d3-force-3d";
import { useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D, { type ForceGraphMethods } from "react-force-graph-2d";
import type { GraphPayload } from "@/lib/types";

const typeColors: Record<string, string> = {
  author: "#d7efe4",
  concept: "#e7c98a",
  question: "#e7b2a4",
  project: "#9bb8ff",
};

const communityColors = ["#7dcea0", "#85c1e9", "#f5b041", "#f1948a", "#c39bd3", "#76d7c4", "#f0b27a", "#aab7b8"];
const labelZoom = 2.4;
const holdMs = 320;

type DrawNode = {
  id: string;
  type: string;
  label: string;
  community: number | null;
  pagerank: number | null;
  x?: number;
  y?: number;
  fx?: number;
  fy?: number;
};

type DrawLink = {
  type?: string;
  source?: string | DrawNode;
  target?: string | DrawNode;
};

function colorFor(node: DrawNode) {
  if (node.type === "paper") return communityColors[(node.community ?? 0) % communityColors.length];
  return typeColors[node.type] ?? "#f3efe6";
}

function radiusFor(node: DrawNode) {
  if (node.type === "paper") return 6 + Math.min(node.pagerank ?? 0, 0.2) * 28;
  if (node.type === "project") return 8;
  if (node.type === "question") return 6;
  return 4;
}

function endpointId(value: string | DrawNode | undefined) {
  if (!value) return "";
  return typeof value === "string" ? value : value.id;
}

export default function GraphView({ graph, onOpen }: { graph: GraphPayload; onOpen: (id: string) => void }) {
  const frame = useRef<HTMLDivElement>(null);
  const graphRef = useRef<ForceGraphMethods | undefined>(undefined);
  const fitted = useRef(false);
  const hoverRef = useRef<DrawNode | null>(null);
  const focusRef = useRef<string | null>(null);
  const neighborhoodRef = useRef<Set<string> | null>(null);
  const [size, setSize] = useState({ width: 800, height: 640 });
  const [hover, setHover] = useState<DrawNode | null>(null);
  const [pointer, setPointer] = useState({ x: 0, y: 0 });
  const [selected, setSelected] = useState<DrawNode | null>(null);

  const data = useMemo(
    () => ({
      nodes: graph.nodes.map((node) => ({ ...node })),
      links: graph.edges.map((edge) => ({ source: edge.source, target: edge.target, type: edge.type })),
    }),
    [graph],
  );

  const adjacency = useMemo(() => {
    const map = new Map<string, Set<string>>();
    for (const edge of graph.edges) {
      const source = edge.source;
      const target = edge.target;
      if (!map.has(source)) map.set(source, new Set());
      if (!map.has(target)) map.set(target, new Set());
      map.get(source)?.add(target);
      map.get(target)?.add(source);
    }
    return map;
  }, [graph]);

  const focusId = selected?.id ?? hover?.id ?? null;
  const neighborhood = useMemo(() => {
    if (!focusId) return null;
    return new Set([focusId, ...(adjacency.get(focusId) ?? [])]);
  }, [adjacency, focusId]);

  hoverRef.current = hover;
  focusRef.current = focusId;
  neighborhoodRef.current = neighborhood;

  useEffect(() => {
    const element = frame.current;
    if (!element) return;
    const observer = new ResizeObserver(() => {
      setSize({ width: element.clientWidth, height: element.clientHeight });
    });
    observer.observe(element);
    setSize({ width: element.clientWidth, height: element.clientHeight });
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    fitted.current = false;
    setSelected(null);
    setHover(null);
    const id = requestAnimationFrame(() => configureForces());
    return () => cancelAnimationFrame(id);
  }, [graph]);

  useEffect(() => {
    const root = frame.current;
    if (!root) return;
    let timer = 0;
    let dragging = false;
    let moved = false;
    let startX = 0;
    let startY = 0;
    let node: DrawNode | null = null;

    const canvas = () => root.querySelector("canvas");

    const down = (event: PointerEvent) => {
      node = hoverRef.current;
      if (!node || event.button !== 0) return;
      event.preventDefault();
      event.stopPropagation();
      dragging = false;
      moved = false;
      startX = event.clientX;
      startY = event.clientY;
      root.setPointerCapture(event.pointerId);
      timer = window.setTimeout(() => {
        dragging = true;
        if (!node) return;
        node.fx = node.x;
        node.fy = node.y;
      }, holdMs);
    };

    const move = (event: PointerEvent) => {
      const bounds = root.getBoundingClientRect();
      setPointer({ x: event.clientX - bounds.left, y: event.clientY - bounds.top });
      if (!node) return;
      if (!dragging && Math.hypot(event.clientX - startX, event.clientY - startY) > 6) {
        moved = true;
        window.clearTimeout(timer);
      }
      if (!dragging) return;
      const rect = canvas()?.getBoundingClientRect();
      const fg = graphRef.current;
      if (!rect || !fg) return;
      const coords = fg.screen2GraphCoords(event.clientX - rect.left, event.clientY - rect.top);
      node.fx = coords.x;
      node.fy = coords.y;
      node.x = coords.x;
      node.y = coords.y;
    };

    const up = (event: PointerEvent) => {
      window.clearTimeout(timer);
      if (node && dragging) {
        node.fx = node.x;
        node.fy = node.y;
      } else if (node && !moved) {
        focusNode(node);
      }
      dragging = false;
      node = null;
      if (root.hasPointerCapture(event.pointerId)) root.releasePointerCapture(event.pointerId);
    };

    root.addEventListener("pointerdown", down, true);
    root.addEventListener("pointermove", move);
    root.addEventListener("pointerup", up);
    return () => {
      window.clearTimeout(timer);
      root.removeEventListener("pointerdown", down, true);
      root.removeEventListener("pointermove", move);
      root.removeEventListener("pointerup", up);
    };
  }, [graph]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") release();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  function configureForces() {
    const fg = graphRef.current;
    if (!fg) return;
    const charge = fg.d3Force("charge") as { strength?: (value: number) => void } | undefined;
    charge?.strength?.(-280);
    const link = fg.d3Force("link") as {
      distance?: (value: (edge: DrawLink) => number) => void;
      strength?: (value: number) => void;
    } | undefined;
    link?.distance?.((edge) => (edge.type === "cites" ? 52 : 88));
    link?.strength?.(0.18);
    fg.d3Force("collide", forceCollide((node) => radiusFor(node as DrawNode) + 12) as never);
    fg.d3Force("x", forceX((node) => ((node as DrawNode).community ?? 0) * 320).strength(0.22) as never);
    fg.d3ReheatSimulation();
  }

  function zoomBy(factor: number) {
    const fg = graphRef.current;
    if (!fg) return;
    fg.zoom(Math.min(8, Math.max(0.15, fg.zoom() * factor)), 220);
  }

  function fit() {
    setSelected(null);
    graphRef.current?.zoomToFit(500, 60);
  }

  function release() {
    setSelected(null);
    graphRef.current?.zoomToFit(500, 60);
  }

  function focusNode(node: DrawNode) {
    setSelected(node);
    const fg = graphRef.current;
    if (!fg || node.x === undefined || node.y === undefined) return;
    fg.centerAt(node.x, node.y, 450);
    fg.zoom(Math.max(fg.zoom(), 3.2), 450);
  }

  return (
    <div ref={frame} className="relative h-full w-full">
      <ForceGraph2D
        ref={graphRef}
        width={size.width}
        height={size.height}
        graphData={data}
        backgroundColor="#171512"
        cooldownTicks={280}
        d3AlphaDecay={0.02}
        d3VelocityDecay={0.35}
        autoPauseRedraw={false}
        enableNodeDrag={false}
        onEngineTick={configureForces}
        onEngineStop={() => {
          if (fitted.current) return;
          fitted.current = true;
          graphRef.current?.zoomToFit(400, 60);
        }}
        nodeLabel={() => ""}
        linkCanvasObject={(link, context) => {
          const edge = link as DrawLink;
          const source = edge.source as DrawNode;
          const target = edge.target as DrawNode;
          const focus = focusRef.current;
          const incident = !focus || source.id === focus || target.id === focus;
          context.save();
          context.globalAlpha = incident ? 0.9 : 0.05;
          context.strokeStyle = edge.type === "cites" ? "#8ee0b8" : "#e7c98a";
          context.lineWidth = incident ? 1.6 : 0.4;
          context.beginPath();
          context.moveTo(source.x ?? 0, source.y ?? 0);
          context.lineTo(target.x ?? 0, target.y ?? 0);
          context.stroke();
          context.restore();
        }}
        nodeCanvasObject={(node, context, scale) => {
          const item = node as DrawNode;
          const radius = radiusFor(item);
          const x = item.x ?? 0;
          const y = item.y ?? 0;
          const focus = focusRef.current;
          const keep = !focus || neighborhoodRef.current?.has(item.id);
          const active = item.id === focus || item.id === hoverRef.current?.id;
          context.save();
          context.globalAlpha = keep ? 1 : 0.07;
          if (active) {
            context.beginPath();
            context.arc(x, y, radius + 5, 0, 2 * Math.PI);
            context.strokeStyle = "#faf7f2";
            context.lineWidth = 1.6;
            context.stroke();
          }
          context.beginPath();
          context.arc(x, y, radius, 0, 2 * Math.PI);
          context.fillStyle = colorFor(item);
          context.fill();
          if (keep && (scale >= labelZoom || active)) {
            const fontSize = Math.max(12 / scale, 3);
            context.font = `${fontSize}px Outfit, sans-serif`;
            context.fillStyle = "rgba(243,239,230,0.95)";
            context.textAlign = "left";
            context.textBaseline = "middle";
            const text = item.label.length > 52 ? `${item.label.slice(0, 52)}…` : item.label;
            context.fillText(text, x + radius + 3, y);
          }
          context.restore();
        }}
        nodePointerAreaPaint={(node, paint, context) => {
          const item = node as DrawNode;
          context.fillStyle = paint;
          context.beginPath();
          context.arc(item.x ?? 0, item.y ?? 0, radiusFor(item) + 6, 0, 2 * Math.PI);
          context.fill();
        }}
        onNodeHover={(node) => {
          const next = (node as DrawNode | null) ?? null;
          setHover((current) => (current?.id === next?.id ? current : next));
        }}
        onBackgroundClick={release}
      />
      {hover && (
        <div
          className="pointer-events-none absolute z-20 max-w-sm rounded-xl border border-black/[0.06] bg-white px-3 py-2 text-sm text-ink shadow-lg"
          style={{ left: Math.min(pointer.x + 16, size.width - 240), top: Math.min(pointer.y + 16, size.height - 72) }}
        >
          <p className="text-[10px] uppercase tracking-[0.14em] text-mute">{hover.type}</p>
          <p className="mt-1 leading-5">{hover.label}</p>
        </div>
      )}
      <div className="absolute bottom-4 left-4 z-20 flex flex-col gap-2">
        <MapButton label="Zoom in" onClick={() => zoomBy(1.45)}>
          +
        </MapButton>
        <MapButton label="Zoom out" onClick={() => zoomBy(0.7)}>
          −
        </MapButton>
        <MapButton label="Fit the map" onClick={fit}>
          ⌂
        </MapButton>
      </div>
      {selected && (
        <div className="absolute left-4 right-4 top-4 z-20 flex items-start justify-between gap-3 rounded-2xl bg-neutral-50/95 px-4 py-3 text-ink shadow-lg">
          <div>
            <p className="text-[10px] uppercase tracking-[0.14em] text-mute">{selected.type}</p>
            <p className="mt-1 text-sm leading-5">{selected.label}</p>
            <p className="mt-1 text-xs text-mute">
              {(adjacency.get(selected.id)?.size ?? 0)} connected. Hold a node, then drag it.
            </p>
            <button className="mt-2 text-sm font-medium" type="button" onClick={() => onOpen(selected.id)}>
              Open record
            </button>
          </div>
          <button
            className="grid h-8 w-8 place-items-center rounded-full border border-black/10 bg-white text-xs"
            type="button"
            aria-label="Leave this node"
            onClick={release}
          >
            Esc
          </button>
        </div>
      )}
    </div>
  );
}

function MapButton({ label, onClick, children }: { label: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      className="grid h-10 w-10 place-items-center rounded-full bg-white text-lg text-ink shadow-md"
    >
      {children}
    </button>
  );
}
