import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Providers from "@/components/Providers";
import ProgressBar from "@/components/ProgressBar";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "LegiLens Colorado",
  description: "Transparency tool for the Colorado General Assembly",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:p-2 focus:bg-white focus:text-blue-700"
        >
          Skip to main content
        </a>
        <Providers>
          <ProgressBar />
          <main id="main">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
