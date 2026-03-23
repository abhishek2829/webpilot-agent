import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "WebPilot Agent — AI Browser Agents That Automate the Web Tasks You Hate",
  description:
    "7 AI agents that automate SaaS setup, research, sales outreach, marketing, and finance. Human approval at every critical step. Open source.",
  openGraph: {
    title: "WebPilot Agent",
    description: "Stop clicking. Start shipping. 7 AI browser agents, 33 workflows, 8 pipelines.",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "WebPilot Agent",
    description: "AI browser agents that automate the web tasks you hate.",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-gray-950 text-gray-100">
        {children}
      </body>
    </html>
  );
}
