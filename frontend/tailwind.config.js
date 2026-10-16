/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#080D19",
        canvas: "#101626",
        panel: "#050505",
        card: "#141414",
        field: "#202431",
        coral: "#E85B66",
        teal: "#37B99A",
        gold: "#E9C45B",
        muted: "#8B919C",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
}
