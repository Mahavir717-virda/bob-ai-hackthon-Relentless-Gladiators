/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        canvas: "var(--bg-canvas)",
        surface: {
          DEFAULT: "var(--bg-surface)",
          muted: "var(--bg-surface-muted)",
        },
        border: {
          DEFAULT: "var(--border-default)",
        },
        primary: "var(--text-primary)",
        secondary: "var(--text-secondary)",
        tertiary: "var(--text-tertiary)",
        copper: {
          DEFAULT: "var(--accent-copper)",
          hover: "var(--accent-copper-hover)",
          subtle: "var(--accent-copper-subtle)",
        },
        spectrum: {
          radar: "#1B8A8A",
          tech: "#7C4A8C",
          rust: "#C1432E",
          amber: "#D89B3C",
          moss: "#3F7A54",
          teal: "#1F9E82",
          bronze: "#8C6A3F",
          sage: "#4F6B52",
        },
        semantic: {
          error: "var(--color-error)",
          warning: "var(--color-warning)",
          success: "var(--color-success)",
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        metric: ['Fraunces', 'Roboto Slab', 'Georgia', 'serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
      },
    },
  },
  plugins: [],
}
