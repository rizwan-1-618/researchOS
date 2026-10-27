import Image from "next/image";

export const authField =
  "w-full border-b border-neutral-300 bg-transparent py-2 text-[15px] text-neutral-900 outline-none focus:border-neutral-800";

export const authAction = "text-sm font-medium text-neutral-900";

export const authButton =
  "mt-8 w-full rounded-xl bg-[#1c2b66] px-4 py-3.5 text-base text-white disabled:opacity-60";

export function AuthFrame({
  children,
  footer,
}: {
  children: React.ReactNode;
  footer: React.ReactNode;
}) {
  return (
    <main className="min-h-screen bg-[#e8edf2] p-3 sm:p-4">
      <div className="grid min-h-[calc(100vh-1.5rem)] overflow-hidden rounded-[1.75rem] border border-black/5 bg-white shadow-[0_10px_40px_rgba(22,32,51,0.06)] sm:min-h-[calc(100vh-2rem)] md:grid-cols-2">
        <div className="relative min-h-[46vh] md:min-h-0">
          <Image
            src="/login-landscape.jpg"
            alt="A tree on a green hill under a cloud"
            fill
            priority
            sizes="(min-width: 768px) 50vw, 100vw"
            className="object-cover"
          />
          <p className="pointer-events-none absolute top-[88%] left-1/2 -translate-x-1/2 pl-[0.45em] text-4xl font-light tracking-[0.45em] text-white drop-shadow-[0_1px_8px_rgba(10,24,14,0.35)] sm:text-5xl">
            WELCOME
          </p>
        </div>
        <div className="flex flex-col px-8 py-12 sm:px-14 lg:px-20">
          <div className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center">{children}</div>
          <p className="pt-8 text-center text-sm text-neutral-900">{footer}</p>
        </div>
      </div>
    </main>
  );
}
