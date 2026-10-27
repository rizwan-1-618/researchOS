import type { Metadata } from "next";
import { Newsreader, Outfit } from "next/font/google";
import { Providers } from "@/components/ui";
import "./globals.css";

const outfit = Outfit({ subsets: ["latin"], variable: "--font-outfit" });
const newsreader = Newsreader({ subsets: ["latin"], variable: "--font-newsreader" });

export const metadata: Metadata = {
  title: "ResearchOS",
  description: "A workspace for discovering, reading, and connecting academic literature.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${outfit.variable} ${newsreader.variable}`}>
      <body className="min-h-screen antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
