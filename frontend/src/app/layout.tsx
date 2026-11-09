import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";

export const metadata: Metadata = {
  title: "Namma Exodus — Crowd Exit Command Centre",
  description:
    "Agentic AI-powered crowd-exit prediction and multi-modal transport coordination for Bengaluru.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="h-full">
      <body className="h-full bg-bg-base text-text-primary font-sans antialiased">
        <Providers>
          <div className="flex flex-col h-full">
            {/* Top navigation bar — 64px */}
            <TopBar />

            <div className="flex flex-1 overflow-hidden">
              {/* Left sidebar */}
              <Sidebar />

              {/* Main content area */}
              <main className="flex-1 overflow-y-auto bg-bg-base">
                {children}
              </main>
            </div>
          </div>
        </Providers>
      </body>
    </html>
  );
}
