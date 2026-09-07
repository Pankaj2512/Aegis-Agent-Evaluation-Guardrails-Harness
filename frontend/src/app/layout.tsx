import type { Metadata, Viewport } from "next";
import dynamic from "next/dynamic";
import { IBM_Plex_Sans, IBM_Plex_Mono } from "next/font/google";

const plexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-geist-sans",
  display: "swap",
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-geist-mono",
  display: "swap",
});
import { MotionProvider } from "@/components/providers/MotionProvider";
import { AppShell } from "@/components/layout/AppShell";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ObservabilityStreamProvider } from "@/providers/ObservabilityStreamProvider";
import { QueryProvider } from "@/providers/QueryProvider";
import { ThemeProvider } from "@/providers/ThemeProvider";
import "./globals.css";

const Toaster = dynamic(
  () => import("@/components/ui/toaster").then((mod) => mod.Toaster),
  { ssr: false }
);

const appUrl = process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000";

/** Inline bootstrap: apply stored theme before paint (avoids light/dark flash). */
const themeInitScript = `(function(){try{var t=localStorage.getItem("aegis-theme");if(t!=="light"&&t!=="dark")t="dark";var r=document.documentElement;r.classList.remove("light","dark");r.classList.add(t);r.style.colorScheme=t;}catch(e){document.documentElement.classList.add("dark");document.documentElement.style.colorScheme="dark";}})();`;

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#e9e5de" },
    { media: "(prefers-color-scheme: dark)", color: "#10110f" },
  ],
  colorScheme: "dark light",
  width: "device-width",
  initialScale: 1,
};

export const metadata: Metadata = {
  metadataBase: new URL(appUrl),
  title: {
    default: "Aegis — Visual Agent Development",
    template: "%s · Aegis",
  },
  description:
    "Build, run, and evaluate agent workflows with guardrails, observability, and human-in-the-loop approvals.",
  keywords: [
    "agent workflows",
    "LLM",
    "evaluation",
    "guardrails",
    "observability",
    "visual canvas",
  ],
  authors: [{ name: "Aegis" }],
  creator: "Aegis",
  openGraph: {
    type: "website",
    locale: "en_US",
    url: appUrl,
    siteName: "Aegis",
    title: "Aegis — Visual Agent Development",
    description:
      "Build, run, and evaluate agent workflows with guardrails, observability, and human-in-the-loop approvals.",
  },
  twitter: {
    card: "summary_large_image",
    title: "Aegis — Visual Agent Development",
    description:
      "Build, run, and evaluate agent workflows with guardrails, observability, and human-in-the-loop approvals.",
  },
  robots: {
    index: true,
    follow: true,
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
      suppressHydrationWarning
      className={`dark ${plexSans.variable} ${plexMono.variable}`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className="min-h-screen bg-background font-sans antialiased">
        <ThemeProvider>
          <MotionProvider>
            <TooltipProvider>
              <QueryProvider>
                <ObservabilityStreamProvider>
                  <AppShell>{children}</AppShell>
                </ObservabilityStreamProvider>
              </QueryProvider>
            </TooltipProvider>
          </MotionProvider>
          <Toaster />
        </ThemeProvider>
      </body>
    </html>
  );
}
