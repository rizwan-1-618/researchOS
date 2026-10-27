"use client";

import dynamic from "next/dynamic";
import { useParams } from "next/navigation";

const Reader = dynamic(() => import("@/components/reader"), { ssr: false });

export default function ReadPage() {
  const params = useParams<{ id: string }>();
  return <Reader paperId={params.id} />;
}
