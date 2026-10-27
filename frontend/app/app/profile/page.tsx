"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Button, ErrorText, Field, control, label, useRefresh } from "@/components/ui";
import { api } from "@/lib/api";
import type { Meta, User } from "@/lib/types";

export default function ProfilePage() {
  const refresh = useRefresh();
  const me = useQuery({ queryKey: ["me"], queryFn: () => api<User>("/api/auth/me") });
  const meta = useQuery({ queryKey: ["meta"], queryFn: () => api<Meta>("/api/meta") });
  const [error, setError] = useState<unknown>(null);
  const user = me.data;
  if (!user) return null;
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-[2rem] font-medium tracking-tight">Research profile</h1>
      <form className="space-y-4 rounded-[1.75rem] border border-black/[0.06] bg-white p-5" onSubmit={async (event) => {
        event.preventDefault();
        const form = new FormData(event.currentTarget);
        const list = (name: string) => String(form.get(name) ?? "").split(",").map((item) => item.trim()).filter(Boolean);
        try {
          await api("/api/users/me", { method: "PATCH", body: JSON.stringify({ name: form.get("name"), bio: form.get("bio"), research_level: form.get("research_level") || null }) });
          await api("/api/users/me/profile", { method: "PUT", body: JSON.stringify({ research_interests: list("interests"), skills: list("skills"), preferred_topics: list("topics") }) });
          refresh();
        } catch (caught) { setError(caught); }
      }}>
        <Field label="Name"><input className={control} name="name" defaultValue={user.name} required /></Field>
        <Field label="Research level">
          <select className={control} name="research_level" defaultValue={user.research_level ?? ""}>
            <option value="">Unspecified</option>
            {(meta.data?.research_levels ?? []).map((level) => <option key={level} value={level}>{label(level)}</option>)}
          </select>
        </Field>
        <Field label="Bio"><textarea className={control} name="bio" defaultValue={user.bio ?? ""} /></Field>
        <Field label="Interests"><input className={control} name="interests" defaultValue={user.profile.research_interests.join(", ")} /></Field>
        <Field label="Skills"><input className={control} name="skills" defaultValue={user.profile.skills.join(", ")} /></Field>
        <Field label="Preferred topics"><input className={control} name="topics" defaultValue={user.profile.preferred_topics.join(", ")} /></Field>
        <p className="text-sm text-soft">Separate interests, skills, and topics with commas. They shape recommendations when you ask Discover to include your profile.</p>
        <ErrorText error={error} />
        <Button type="submit">Save profile</Button>
      </form>
    </div>
  );
}
