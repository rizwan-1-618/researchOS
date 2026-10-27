import { Elevator, Riffle, Slow } from "@lucasmarkes/hairline/react";
import Link from "next/link";

const panel = "#f3f3f4";
const plate = { "--hairline-plate": panel } as React.CSSProperties;

export default function HomePage() {
  return (
    <main className="min-h-screen bg-white text-neutral-950">
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col px-5 py-5 md:px-8">
        <header className="flex items-start justify-between gap-6">
          <Link href="/" className="text-xl font-medium tracking-tight">
            ResearchOS
          </Link>
          <nav className="grid grid-cols-2 gap-x-10 gap-y-1 text-sm">
            <Link href="/login">Sign in</Link>
            <Link href="/app/library">Library</Link>
            <Link href="/app/discover">Discover</Link>
            <Link href="/app/graph">Graph</Link>
          </nav>
        </header>

        <section className="mt-6 grid min-h-0 flex-1 gap-4 md:grid-cols-12 md:grid-rows-[minmax(0,1.35fr)_minmax(0,1fr)]">
          <article
            className="flex h-full min-h-0 flex-col overflow-hidden rounded-[1.75rem] md:col-span-5"
            style={{ background: panel }}
          >
            <h1 className="max-w-[16rem] shrink-0 p-6 pb-2 text-[1.65rem] leading-[1.15] font-medium tracking-tight">
              Keep the literature, the notes, and the questions in one room.
            </h1>
            <div className="flex min-h-0 flex-1 items-end justify-center">
              <Riffle label="A tray of cards" theme="light" className="h-full w-auto max-w-full" style={plate} />
            </div>
          </article>

          <article
            className="relative h-full min-h-0 overflow-hidden rounded-[1.75rem] md:col-span-7"
            style={{ background: panel }}
          >
            <div className="relative z-10 max-w-[16rem] p-6">
              <p className="inline-flex items-center rounded-full border border-neutral-300 px-3 py-1 text-xs">Desk</p>
              <p className="mt-4 text-[1.65rem] leading-[1.15] font-medium tracking-tight">
                Search,
                <br />
                Read,
                <br />
                Connect.
              </p>
              <Link href="/register" className="mt-5 inline-flex rounded-full border border-neutral-800 px-4 py-2 text-sm">
                Open a desk
              </Link>
            </div>
            <div className="absolute inset-y-0 right-0 flex w-[58%] items-center justify-center">
              <Elevator label="An elevator between floors" theme="light" className="h-full w-auto max-w-none" style={plate} />
            </div>
          </article>

          <article
            className="grid items-center overflow-hidden rounded-[1.75rem] md:col-span-7 md:grid-cols-2"
            style={{ background: panel }}
          >
            <Slow label="Crates riding a belt" theme="light" className="w-full" style={plate} />
            <div className="p-8">
              <h2 className="max-w-[16rem] text-[1.75rem] leading-[1.15] font-medium tracking-tight">
                A graph you can actually move through.
              </h2>
              <Link href="/register" className="mt-5 inline-flex text-sm text-neutral-600">
                View the desk →
              </Link>
            </div>
          </article>

          <article
            className="grid min-h-52 place-items-center rounded-[1.75rem] md:col-span-5"
            style={{ background: panel }}
          >
            <Link href="/register" className="rounded-full bg-white px-8 py-3 text-sm shadow-sm">
              Let&apos;s go →
            </Link>
          </article>
        </section>
      </div>
    </main>
  );
}
