import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AirCrewAI — Crew Recovery Operations",
  description: "AI-powered crew disruption recovery system — SIMULATED ENVIRONMENT",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-gray-950 text-white min-h-screen">
        {children}
      </body>
    </html>
  );
}
