import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";
import { AppProviders } from "./providers";

export const metadata: Metadata = {
  title: "J-Study Clinical Workbench",
  description: "Source-linked course material generation and reading workspace.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return <html lang="en" className="h-full antialiased"><body className="min-h-full"><AppProviders>{children}</AppProviders></body></html>;
}
