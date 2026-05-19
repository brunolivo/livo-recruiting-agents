import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans:    ["var(--font-inter)", "Inter", "system-ui", "sans-serif"],
        display: ["var(--font-display)", "DM Sans", "system-ui", "sans-serif"],
      },
      colors: {
        livo: {
          primary:        "#007C92",
          "primary-hover":"#005362",
          "primary-light":"#E8F4F7",
          slate:          "#1C2631",
          "text-secondary":"#405263",
          "text-muted":   "#8AA3B8",
          "bg-page":      "#F5F5F2",
          "bg-secondary": "#EDEDE8",
          success:        "#1FC86E",
          danger:         "#EC221F",
          warning:        "#FCC804",
        },
      },
      boxShadow: {
        card: "0 2px 16px 2px rgba(0,0,0,0.10)",
        "card-hover": "0 4px 24px 4px rgba(0,0,0,0.13)",
      },
      borderColor: {
        DEFAULT: "rgba(0,0,0,0.10)",
      },
    },
  },
  plugins: [],
};

export default config;
