/**
 * Latch: a cabinet of three drawers. At rest the middle drawer sits a little
 * proud and its front is bright. The pointer picks a drawer; it slides out
 * and the others ease after it, staggered by distance. Each front has a pull.
 */
const {
  Cam, clamp, facing, fit, prism, proj, rings, tdone, tset, tval, tween,
  disposer, mk, pointer, put, register, solid,
} = HL;

const N = 3, W = 72, DH = 18, DEPTH = 34, GAP = 5, BASE = 8;
const REST = [2, 9, 3], STEP = 46;
const TOP = BASE + N * DH + (N - 1) * GAP;

function mount({ stage, svg, read }, value) {
  const bag = disposer();
  let slide = value;
  const C = Cam(45, 0.5, 2.05);
  fit(C, [[-8, -6, 0], [W + 8, DEPTH + 36, 0], [-8, DEPTH + 36, TOP + 8], [W + 8, -6, TOP + 8]], 200, 166);
  const P = proj(C), front = facing(C);
  const g = mk("g", {}, svg);
  const [shell, shellIn] = rings(-6, -4, W + 6, DEPTH + 2, 2.4, 1);
  const caseBody = solid(g);
  put(caseBody, prism(P, front, shell, shellIn, 0, TOP + 6));

  const drawers = [];
  for (let i = 0; i < N; i++) {
    const frontPlate = solid(g), pull = solid(g);
    drawers.push({ frontPlate, pull, y: tween(REST[i]) });
  }

  function z0(i) { return BASE + i * (DH + GAP); }

  function pose(i, out) {
    const z = z0(i);
    const [face, faceIn] = rings(3, out, W - 3, out + DEPTH, 1.6, 0.7);
    const [knob, knobIn] = rings(W / 2 - 7, out + DEPTH - 5, W / 2 + 7, out + DEPTH + 1.2, 1.1, 0.45);
    return {
      face: prism(P, front, face, faceIn, z, z + DH),
      pull: prism(P, front, knob, knobIn, z + 6, z + DH - 6),
    };
  }

  function draw(i, out) {
    const q = pose(i, out);
    put(drawers[i].frontPlate, q.face);
    put(drawers[i].pull, q.pull);
  }

  const centers = drawers.map((_, i) => P(W / 2, REST[i] + DEPTH / 2, z0(i) + DH / 2));

  function hit([sx, sy]) {
    let best = -1, dist = 42;
    centers.forEach(([x, y], i) => {
      const d = Math.hypot(sx - x, sy - y);
      if (d < dist) { dist = d; best = i; }
    });
    return best;
  }

  const loop = register(stage, (_dt, now) => {
    let moving = false;
    drawers.forEach((drawer, i) => {
      draw(i, tval(drawer.y, now));
      if (!tdone(drawer.y, now)) moving = true;
    });
    return moving;
  });
  bag.add(loop.unregister);

  let act = -1;
  function setActive(a) {
    if (a === act) return;
    const now = performance.now(), from = a >= 0 ? a : act;
    act = a;
    drawers.forEach((drawer, i) => {
      const dist = a < 0 ? 99 : Math.abs(i - a);
      const extra = a < 0 ? 0 : dist === 0 ? slide : dist === 1 ? slide * 0.28 : 0;
      tset(drawer.y, REST[i] + extra, now, Math.abs(i - from) * STEP);
      const on = a < 0 ? i === 1 : i === a;
      drawer.frontPlate.sil.classList.toggle("hi", on);
      drawer.pull.sil.classList.toggle("hi", on);
    });
    read.textContent = a < 0 ? "rest" : "drawer " + (a + 1);
    loop.wake();
  }

  read.textContent = "rest";
  drawers[1].frontPlate.sil.classList.add("hi");
  drawers[1].pull.sil.classList.add("hi");
  bag.add(pointer(stage, { move: (p) => setActive(hit(p)), leave: () => setActive(-1) }));
  bag.add(() => svg.replaceChildren());
  return { set: (v) => { slide = clamp(v, 6, 26); }, destroy: bag.dispose };
}

hairline({
  name: "latch",
  means: "Three drawers in a cabinet: the one under the pointer slides out, and its neighbours ease after it.",
  rules: [1, 2, 5, 9],
  range: [6, 14, 26],
  tour: [[238, 155], [209, 134], [188, 91], null],
  mount,
});
