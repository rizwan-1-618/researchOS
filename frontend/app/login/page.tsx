"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AuthFrame, authAction, authButton, authField } from "@/components/auth-frame";
import { ApiError, api } from "@/lib/api";
import { ErrorText } from "@/components/ui";

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setPending(true);
    setError(null);
    try {
      await api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: form.get("email"), password: form.get("password") }),
      });
      router.push("/app");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught : new Error("Could not sign in"));
    } finally {
      setPending(false);
    }
  }

  return (
    <AuthFrame
      footer={
        <>
          Don&apos;t have an account?{" "}
          <Link href="/register" className={authAction}>
            Sign up
          </Link>
        </>
      }
    >
      <form onSubmit={submit}>
        <h1 className="text-center text-5xl font-medium tracking-tight text-neutral-950">Login</h1>
        <div className="mt-14">
          <label htmlFor="email" className="block text-[15px] text-neutral-500">
            Email
          </label>
          <input id="email" className={authField} name="email" type="email" autoComplete="email" required />
        </div>
        <div className="mt-10">
          <div className="flex items-baseline justify-between gap-4">
            <label htmlFor="password" className="text-[15px] text-neutral-500">
              Password
            </label>
            <span className={authAction}>Forgot password?</span>
          </div>
          <input
            id="password"
            className={authField}
            name="password"
            type="password"
            autoComplete="current-password"
            required
          />
        </div>
        <div className="mt-4">
          <ErrorText error={error} />
        </div>
        <button type="submit" disabled={pending} className={authButton}>
          {pending ? "Signing in" : "Login"}
        </button>
      </form>
    </AuthFrame>
  );
}
