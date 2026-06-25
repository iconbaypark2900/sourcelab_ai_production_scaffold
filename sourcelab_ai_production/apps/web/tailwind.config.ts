import type { Config } from "tailwindcss";

/**
 * Tailwind v4 auto-detects content, but we declare it explicitly so the
 * Run Studio class scanning is deterministic. The diffusion-console visual
 * language lives mostly in styles/globals.css; this file keeps a few shared
 * design tokens available as standard utilities.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        field: {
          cyan: "#22d3ee",
          violet: "#a855f7",
          ink: "#070b16",
        },
      },
      fontFamily: {
        mono: [
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Consolas",
          "Liberation Mono",
          "monospace",
        ],
      },
    },
  },
};

export default config;
