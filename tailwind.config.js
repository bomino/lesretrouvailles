/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./core/**/*.{html,py}",
  ],
  theme: {
    extend: {
      fontSize: {
        // Accessibility baseline: bump base from 14px → 16px (spec §8.3)
        base: ["16px", { lineHeight: "1.6" }],
      },
      minHeight: {
        // Tactile target floor (spec §8.3)
        tap: "44px",
      },
      minWidth: {
        tap: "44px",
      },
    },
  },
  plugins: [require("daisyui")],
  daisyui: {
    themes: ["light"],
    logs: false,
  },
};
