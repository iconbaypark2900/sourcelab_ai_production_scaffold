import type { Metadata } from "next";
import type { ReactNode } from "react";

import "../styles/globals.css";
import { AppNav } from "@/components/Chrome";

export const metadata: Metadata = {
  title: "SourceLab Run Studio",
  description:
    "Source-grounded generation console for SourceLab AI runs — approved sources to proof bundle to learning update.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AppNav />
        {children}
      </body>
    </html>
  );
}
