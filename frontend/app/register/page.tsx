"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AuthFrame, authAction, authButton, authField } from "@/components/auth-frame";
import { api } from "@/lib/api";
import { ErrorText } from "@/components/ui";

export default function RegisterPage() {
  const router = useRouter();
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setPending(true);
    setError(null);
    try {
      await api("/api/auth/register", {
        method: "POST",
        body: JSON.stringify({
          name: form.get("name"),
          email: form.get("email"),
          password: form.get("password"),
        }),
      });
      router.push("/app/profile");
    } catch (caught) {
      setError(caught);
    } finally {
      setPending(false);
    }
  }

  return (
    <AuthFrame
      footer={
        <>
          Already registered?{" "}
          <Link href="/login" className={authAction}>
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={submit}>
        <h1 className="text-center text-5xl font-medium tracking-tight text-neutral-950">Sign up</h1>
        <div className="mt-14">
          <label htmlFor="name" className="block text-[15px] text-neutral-500">
            Name
          </label>
          <input id="name" className={authField} name="name" autoComplete="name" required />
        </div>
        <div className="mt-10">
          <label htmlFor="email" className="block text-[15px] text-neutral-500">
            Email
          </label>
          <input id="email" className={authField} name="email" type="email" autoComplete="email" required />
        </div>
        <div className="mt-10">
          <label htmlFor="password" className="block text-[15px] text-neutral-500">
            Password
          </label>
          <input
            id="password"
            className={authField}
            name="password"
            type="password"
            autoComplete="new-password"
            minLength={8}
            required
          />
        </div>
        <div className="mt-4">
          <ErrorText error={error} />
        </div>
        <button type="submit" disabled={pending} className={authButton}>
          {pending ? "Signing up" : "Sign up"}
        </button>
      </form>
    </AuthFrame>
  );
}
