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
        grid: {
          dark: "#0b0f19",
          card: "#111827",
          border: "#1f293d",
          accent: "#38bdf8",
        },
      },
    },
  },
  plugins: [],
}
