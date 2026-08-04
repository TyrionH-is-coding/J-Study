import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AppShell } from "@/components/shell/app-shell";
import "@/styles/globals.css";
import { AppProviders } from "./providers";

export const metadata: Metadata = {
  title: "J-Study",
  description: "Multi-discipline learning workspace foundation.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AppProviders>
          <AppShell>{children}</AppShell>
        </AppProviders>
      </body>
    </html>
  );
}
