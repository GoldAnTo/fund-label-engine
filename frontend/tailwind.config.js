/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "oklch(0.985 0.002 250)",
        surface: "oklch(1.00 0 0)",
        "surface-2": "oklch(0.96 0.003 250)",
        "surface-3": "oklch(0.93 0.003 250)",
        border: "oklch(0.90 0.004 250)",
        "border-2": "oklch(0.82 0.005 250)",
        text: "oklch(0.20 0.01 250)",
        "text-2": "oklch(0.45 0.008 250)",
        "text-3": "oklch(0.60 0.006 250)",
        accent: "oklch(0.52 0.18 255)",
        "accent-soft": "oklch(0.94 0.03 255)",
        "accent-text": "oklch(0.45 0.16 255)",
        pos: "oklch(0.50 0.15 155)",
        "pos-soft": "oklch(0.94 0.03 155)",
        "pos-text": "oklch(0.40 0.13 155)",
        warn: "oklch(0.62 0.15 65)",
        "warn-soft": "oklch(0.95 0.03 65)",
        "warn-text": "oklch(0.48 0.13 62)",
        neg: "oklch(0.52 0.18 28)",
        "neg-soft": "oklch(0.94 0.03 28)",
        "neg-text": "oklch(0.45 0.16 28)",
      },
      fontFamily: {
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "Helvetica Neue", "PingFang SC", "Microsoft YaHei", "sans-serif"],
        mono: ["SF Mono", "Fira Code", "monospace"],
      },
    },
  },
  plugins: [],
}
