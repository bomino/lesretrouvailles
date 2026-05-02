const theme = require("./tailwind.theme.json");
const tokens = (theme.theme && theme.theme.extend) || theme;

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./core/**/*.{html,py}",
  ],
  theme: {
    extend: {
      // Tokens from DESIGN.md (single source of truth for visual identity)
      ...(tokens.colors && { colors: tokens.colors }),
      ...(tokens.fontFamily && { fontFamily: tokens.fontFamily }),
      ...(tokens.fontSize && { fontSize: tokens.fontSize }),
      ...(tokens.borderRadius && { borderRadius: tokens.borderRadius }),
      ...(tokens.spacing && { spacing: tokens.spacing }),
      // Project-specific extensions not expressed in DESIGN.md
      minHeight: { tap: "44px" },
      minWidth: { tap: "44px" },
    },
  },
  plugins: [require("daisyui")],
  daisyui: {
    themes: ["light"],
    logs: false,
  },
};
