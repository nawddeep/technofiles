/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        "primary": "#9f4042",
        "primary-dim": "#ffbaba",
        "secondary": "#9c41c1",
        "secondary-dim": "#ce7eec",
        "tertiary": "#6e5d00",
        "tertiary-dim": "#f5e19e",
        "background": "#fef7ff",
        "surface": "#fef7ff",
        "surface-variant": "#e7e0ec",
        "on-surface": "#1d1a22",
        "on-surface-variant": "#49454f",
        "outline-variant": "#cac4d0",
        "on-primary": "#ffffff",
      },
      fontFamily: {
        "headline": ["Epilogue", "sans-serif"],
        "body": ["Inter", "sans-serif"],
        "label": ["Inter", "sans-serif"]
      }
    },
  },
  plugins: [],
}
