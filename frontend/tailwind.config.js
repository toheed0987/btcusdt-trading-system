/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "#0b0e14",
        panel: "#131722",
        border: "#232838",
        buy: "#16c784",
        sell: "#ea3943",
        hold: "#f2b705",
        accent: "#4f8cff",
      },
    },
  },
  plugins: [],
};
