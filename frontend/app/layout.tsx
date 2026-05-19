import type { Metadata, Viewport } from "next";
import { Inter, DM_Sans } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const dmSans = DM_Sans({ subsets: ["latin"], variable: "--font-display" });

export const metadata: Metadata = {
  title: "Livo Hunter — AI Recruiting",
  description: "AI-powered recruiting pipeline for Livo Health",
};

export const viewport: Viewport = {
  themeColor: "#007C92",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body
        className={`${inter.variable} ${dmSans.variable} font-sans bg-[#F5F5F2] text-[#1C2631] antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
