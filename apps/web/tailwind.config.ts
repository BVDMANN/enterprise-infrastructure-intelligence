import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Enterprise palette (see docs — UX specification, PHASE 1):
        // deep navy / marine + blue accent, neutral greys.
        navy: {
          950: "#0a1128",
          900: "#0f1e46",
          800: "#1b2f5e",
        },
        accent: {
          DEFAULT: "#2563eb",
          dark: "#1d4ed8",
        },
      },
    },
  },
  plugins: [],
};

export default config;
