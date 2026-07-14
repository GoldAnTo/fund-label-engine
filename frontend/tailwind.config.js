/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // 语义色：低饱和，投研工具风格
        bg: "oklch(0.965 0.003 250)",
        surface: "oklch(0.992 0.002 250)",
        "surface-2": "oklch(0.948 0.005 250)",
        "surface-3": "oklch(0.928 0.006 250)",
        border: "oklch(0.872 0.005 250)",
        "border-2": "oklch(0.768 0.008 250)",
        text: "oklch(0.15 0.008 250)",
        "text-2": "oklch(0.42 0.008 250)",
        "text-3": "oklch(0.58 0.005 250)",
        accent: "oklch(0.48 0.12 245)",
        "accent-soft": "oklch(0.93 0.025 245)",
        "accent-text": "oklch(0.34 0.08 245)",
        pos: "oklch(0.52 0.12 155)",
        "pos-soft": "oklch(0.92 0.035 155)",
        "pos-text": "oklch(0.28 0.08 155)",
        warn: "oklch(0.58 0.12 65)",
        "warn-soft": "oklch(0.93 0.04 65)",
        "warn-text": "oklch(0.38 0.10 62)",
        neg: "oklch(0.52 0.12 25)",
        "neg-soft": "oklch(0.92 0.035 25)",
        "neg-text": "oklch(0.28 0.08 25)",
      },
      fontFamily: {
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "Helvetica Neue", "PingFang SC", "Microsoft YaHei", "sans-serif"],
        mono: ["SF Mono", "Fira Code", "monospace"],
      },
    },
  },
  plugins: [],
}
