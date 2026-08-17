/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          green: "#00C48C",
          dark: "#0D1117",
          card: "#161B22",
          border: "#30363D",
          muted: "#8B949E",
        }
      },
      fontFamily: {
        mono: ["JetBrains Mono", "monospace"],
      }
    },
  },
  plugins: [],
};
