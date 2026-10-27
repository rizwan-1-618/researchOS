/**
 * Shelf: five volumes on a desk plate. At rest they stand at uneven heights
 * and the middle one is bright. The pointer picks a volume; it rises and the
 * ones beside it follow, staggered by distance. A ribbon marks each spine.
 */
const {
  Cam, clamp, facing, fit, prism, proj, rings, tdone, tset, tval, tween,
  disposer, mk, pointer, put, register, solid,
} = HL;

const N = 5, T = 16, D = 44, H = 60, GAP = 7, PITCH = T + GAP;
const REST = [2, 5, 11, 4, 1], LIFT = 18, STEP = 42;
const X1 = (N - 1) * PITCH + T;

function mount({ stage, svg, read }, value) {
  const bag = disposer();
  let reach = value;
  const C = Cam(45, 0.5, 1.86);
  fit(C, [[-10, -8, 0], [X1 + 10, D + 12, 0], [-10, D + 12, H + 36], [X1 + 10, -8, H + 36]], 200, 168);
  const P = proj(C), front = facing(C);
  const g = mk("g", {}, svg);
  const [deck, deckIn] = rings(-12, -8, X1 + 12, D + 10, 3, 1.1);
  const desk = solid(g);
  put(desk, prism(P, front, deck, deckIn, 0, 3.2));

  const books = [];
  for (let i = 0; i < N; i++) {
    const body = solid(g), ribbon = solid(g);
    books.push({ body, ribbon, z: tween(REST[i]) });
  }

  function pose(i, lift) {
    const x0 = i * PITCH;
    const [ring, inner] = rings(x0, 0, x0 + T, D, 1.5, 0.7);
    const [mark, markIn] = rings(x0 + 5.5, D - 8, x0 + 9, D + 5, 0.6, 0.35);
    return {
      body: prism(P, front, ring, inner, 3.2, 3.2 + H + lift),
      ribbon: prism(P, front, mark, markIn, 3.2 + H + lift - 3, 3.2 + H + lift + 11),
    };
  }

  function draw(i, lift) {
    const q = pose(i, lift);
    put(books[i].body, q.body);
    put(books[i].ribbon, q.ribbon);
  }

  const centers = books.map((_, i) => P(i * PITCH + T / 2, D / 2, 3.2 + H + REST[i]));

  function hit([sx, sy]) {
    let best = -1, dist = 36;
    centers.forEach(([x, y], i) => {
      const d = Math.hypot(sx - x, sy - y);
      if (d < dist) { dist = d; best = i; }
    });
    return best;
  }

  const loop = register(stage, (_dt, now) => {
    let moving = false;
    books.forEach((book, i) => {
      draw(i, tval(book.z, now));
      if (!tdone(book.z, now)) moving = true;
    });
    return moving;
  });
  bag.add(loop.unregister);

  let act = -1;
  function setActive(a) {
    if (a === act) return;
    const now = performance.now(), from = a >= 0 ? a : act;
    act = a;
    books.forEach((book, i) => {
      const dist = a < 0 ? 0 : Math.abs(i - a);
      const extra = a < 0 ? 0 : dist === 0 ? reach : dist === 1 ? reach * 0.42 : dist === 2 ? reach * 0.16 : 0;
      tset(book.z, REST[i] + extra, now, Math.abs(i - from) * STEP);
      book.body.sil.classList.toggle("hi", a < 0 ? i === 2 : i === a);
    });
    read.textContent = a < 0 ? "rest" : "vol " + (a + 1);
    loop.wake();
  }

  read.textContent = "rest";
  books[2].body.sil.classList.add("hi");
  bag.add(pointer(stage, { move: (p) => setActive(hit(p)), leave: () => setActive(-1) }));
  bag.add(() => svg.replaceChildren());
  return { set: (v) => { reach = clamp(v, 8, 30); }, destroy: bag.dispose };
}

hairline({
  name: "shelf",
  means: "Five volumes on a desk: the one under the pointer rises, and the volumes beside it follow.",
  rules: [1, 2, 5, 9],
  range: [8, 18, 30],
  tour: [[142, 88], [203, 103], [263, 150], null],
  mount,
});
