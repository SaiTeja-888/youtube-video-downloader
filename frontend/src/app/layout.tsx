import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Providers from "./providers";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "POSTLINK media downloader | Fast Media Extractor",
  description: "Download video, audio, and image media from supported hosting platforms with a frosted glass interface.",
  metadataBase: new URL("http://localhost"),
  alternates: {
    canonical: "/",
  },
  keywords: ["video downloader", "instagram reels downloader", "image downloader", "audio extraction", "download manager", "yt-dlp wrapper"],
  authors: [{ name: "POSTLINK" }],
  openGraph: {
    title: "POSTLINK media downloader - Fast Media Extractor",
    description: "Analyze, extract and download media from supported hosting web pages instantly.",
    url: "/",
    siteName: "POSTLINK media downloader",
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "POSTLINK media downloader",
    description: "Download supported videos, reels, audio, and images instantly.",
  },
  robots: {
    index: true,
    follow: true,
    nocache: false,
    googleBot: {
      index: true,
      follow: true,
      noimageindex: false,
    },
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="scroll-smooth">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased min-h-screen flex flex-col relative`}
      >
        <Providers>
          {children}
        </Providers>
      </body>
    </html>
  );
}
