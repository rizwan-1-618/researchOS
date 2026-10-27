"use client";

import { useEffect, useRef } from "react";

type HairlineFigure = {
  name: string;
  means: string;
  range: [number, number, number];
  mount: (
    host: {
      stage: HTMLElement;
      svg: SVGElement;
      read: { textContent: string };
    },
    value: number,
  ) => { destroy: () => void };
};

type HairlineKernel = {
  inject: (root: Document) => void;
  mk: (tag: string, attrs: Record<string, string>, parent: Element) => SVGElement;
};

declare global {
  interface Window {
    HL?: HairlineKernel;
    hairline?: (figure: HairlineFigure) => void;
  }
}

let ready: Promise<HairlineFigure> | null = null;

function loadScript(src: string) {
  return new Promise<void>((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${src}"]`);
    if (existing) {
      if (existing.dataset.loaded === "true") resolve();
      else existing.addEventListener("load", () => resolve(), { once: true });
      return;
    }
    const script = document.createElement("script");
    script.src = src;
    script.onload = () => {
      script.dataset.loaded = "true";
      resolve();
    };
    script.onerror = () => reject(new Error(src));
    document.head.appendChild(script);
  });
}

function loadShelf() {
  ready ??= new Promise((resolve, reject) => {
    window.hairline = (figure) => resolve(figure);
    loadScript("/hairline/kernel.js")
      .then(() => loadScript("/hairline/shelf.js"))
      .catch(reject);
  });
  return ready;
}

export function ShelfFigure() {
  const stageRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;
    let gone = false;
    let destroy = () => {};

    loadShelf().then((figure) => {
      const kernel = window.HL;
      if (gone || !stageRef.current || !kernel) return;
      const live = document.createElement("span");
      live.setAttribute("data-hairline-live", "");
      stage.appendChild(live);
      const read = {
        get textContent() {
          return live.textContent ?? "";
        },
        set textContent(value: string) {
          live.textContent = value;
        },
      };
      kernel.inject(document);
      stage.dataset.hairline = figure.name;
      stage.dataset.hairlineTheme = "light";
      stage.setAttribute("role", "img");
      stage.setAttribute("aria-label", figure.means);
      const svg = kernel.mk("svg", { viewBox: "0 0 400 320", "aria-hidden": "true" }, stage);
      const handle = figure.mount({ stage, svg, read }, figure.range[1]);
      destroy = () => handle.destroy();
    });

    return () => {
      gone = true;
      destroy();
      stage.replaceChildren();
      delete stage.dataset.hairline;
      delete stage.dataset.hairlineTheme;
    };
  }, []);

  return (
    <div
      ref={stageRef}
      className="aspect-[5/4] w-full bg-transparent"
      style={{ "--hairline-plate": "var(--color-paper)" } as React.CSSProperties}
    />
  );
}
