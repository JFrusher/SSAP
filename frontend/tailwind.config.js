/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#F4EEE2", // page
        sheet: "#FBF8F1", // cards, panels
        ink: "#1F1D1A", // text
        "ink-soft": "#5B554C", // secondary text (6.4:1 on paper)
        crease: "#DDD3C1", // borders, fold lines
        navy: "#24386B", // primary actions (white text 10:1)
        vermilion: "#B83A1E", // recommendation stamp, danger (white text 5.6:1)
        sea: "#1F6F64", // positive actions (white text 5.9:1)
      },
      fontFamily: {
        serif: ["Newsreader", "Georgia", "serif"],
        sans: ["system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
      },
    },
  },
  plugins: [],
};
