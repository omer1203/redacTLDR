import type { Metadata } from "next";
import { Fraunces, Geist, Geist_Mono } from "next/font/google";

import { Providers } from "@/components/providers";
import "./globals.css";

const geistSans = Geist({ subsets: ["latin"], variable: "--font-geist-sans" });
const geistMono = Geist_Mono({ subsets: ["latin"], variable: "--font-geist-mono" });
const fraunces = Fraunces({ subsets: ["latin"], weight: ["500", "600"], variable: "--font-fraunces" });

export const metadata: Metadata = {
  title: "RedacTLDR",
  description: "Share documents without sharing yourself.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning className={`${geistSans.variable} ${geistMono.variable} ${fraunces.variable}`}>
      <body className="font-sans">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
