const theme = require("./tailwind.theme.json");
const tokens = (theme.theme && theme.theme.extend) || theme;

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./core/**/*.{html,py}",
    "./members/**/*.{html,py}",
    "./cooptation/**/*.{html,py}",
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
  plugins: [require("@tailwindcss/typography"), require("daisyui")],
  daisyui: {
    themes: [
      {
        alumni: {
          // Map DaisyUI semantic slots to DESIGN.md tokens.
          // DaisyUI components (btn-primary, alert-info, etc.) now render
          // in brand colors instead of DaisyUI defaults.
          primary: tokens.colors.tertiary,
          "primary-content": tokens.colors["on-tertiary"],
          secondary: tokens.colors["whatsapp-green"],
          "secondary-content": tokens.colors["on-whatsapp-green"],
          accent: tokens.colors["ceremonial-gold"],
          "accent-content": tokens.colors["on-ceremonial-gold"],
          neutral: tokens.colors.primary,
          "neutral-content": tokens.colors["on-primary"],
          "base-100": tokens.colors.neutral,
          "base-200": tokens.colors["surface-variant"],
          "base-300": tokens.colors.surface,
          "base-content": tokens.colors.primary,
          info: tokens.colors["whatsapp-green"],
          success: tokens.colors["whatsapp-green"],
          warning: tokens.colors["ceremonial-gold"],
          error: "#B91C1C",
        },
      },
    ],
    logs: false,
  },
};
