/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "oklch(0.16 0.005 250)",
        surface: "oklch(0.20 0.006 250)",
        "surface-2": "oklch(0.24 0.006 250)",
        "surface-3": "oklch(0.28 0.006 250)",
        border: "oklch(0.32 0.006 250)",
        "border-2": "oklch(0.42 0.008 250)",
        text: "oklch(0.92 0.004 250)",
        "text-2": "oklch(0.68 0.006 250)",
        "text-3": "oklch(0.52 0.005 250)",
        accent: "oklch(0.62 0.14 245)",
        "accent-soft": "oklch(0.30 0.04 245)",
        "accent-text": "oklch(0.72 0.10 245)",
        pos: "oklch(0.62 0.14 155)",
        "pos-soft": "oklch(0.30 0.04 155)",
        "pos-text": "oklch(0.72 0.10 155)",
        warn: "oklch(0.68 0.14 65)",
        "warn-soft": "oklch(0.30 0.04 65)",
        "warn-text": "oklch(0.78 0.12 62)",
        neg: "oklch(0.58 0.16 28)",
        "neg-soft": "oklch(0.30 0.04 28)",
        "neg-text": "oklch(0.68 0.14 28)",
      },
      fontFamily: {
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "Helvetica Neue", "PingFang SC", "Microsoft YaHei", "sans-serif"],
        mono: ["SF Mono", "Fira Code", "monospace"],
      },
    },
  },
  plugins: [],
}
