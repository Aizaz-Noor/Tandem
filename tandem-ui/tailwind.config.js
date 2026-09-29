/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  "#f0f9ff",
          100: "#e0f2fe",
          200: "#bae6fd",
          300: "#7dd3fc",
          400: "#38bdf8",
          500: "#0ea5e9",
          600: "#0284c7",
          700: "#0369a1",
          800: "#075985",
          900: "#0c4a6e",
          950: "#082f49",
        },
        glass: {
          bg:     "rgba(255,255,255,0.06)",
          border: "rgba(255,255,255,0.12)",
          hover:  "rgba(255,255,255,0.10)",
        }
      },
      backdropBlur: {
        xs: "2px",
        "3xl": "64px",
      },
      fontFamily: {
        sans: [
          "Inter",
          "SF Pro Display",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "sans-serif",
        ],
        mono: ["JetBrains Mono", "Fira Code", "Consolas", "monospace"],
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4,0,0.6,1) infinite",
        "spin-slow":  "spin 3s linear infinite",
        "glow":       "glow 2s ease-in-out infinite alternate",
        "slide-in":   "slideIn 0.3s ease-out",
        "fade-up":    "fadeUp 0.4s ease-out",
      },
      keyframes: {
        glow: {
          "0%":   { "box-shadow": "0 0 8px rgba(14,165,233,0.4)" },
          "100%": { "box-shadow": "0 0 24px rgba(14,165,233,0.8)" },
        },
        slideIn: {
          "0%":   { transform: "translateX(-100%)", opacity: "0" },
          "100%": { transform: "translateX(0)",      opacity: "1" },
        },
        fadeUp: {
          "0%":   { transform: "translateY(16px)", opacity: "0" },
          "100%": { transform: "translateY(0)",    opacity: "1" },
        },
      },
      backgroundImage: {
        "mesh-gradient":
          "radial-gradient(at 27% 37%, hsla(215,98%,61%,0.15) 0px, transparent 50%)," +
          "radial-gradient(at 97% 21%, hsla(125,98%,72%,0.08) 0px, transparent 50%)," +
          "radial-gradient(at 52% 99%, hsla(354,98%,61%,0.08) 0px, transparent 50%)," +
          "radial-gradient(at 10% 29%, hsla(189,96%,67%,0.12) 0px, transparent 50%)",
      },
    },
  },
  plugins: [],
}
