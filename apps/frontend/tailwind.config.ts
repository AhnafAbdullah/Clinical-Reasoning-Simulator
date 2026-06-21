import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Creamy matte white surfaces
        cream: {
          DEFAULT: "#F7F2E7", // page background
          card: "#FFFDF8", // raised cards
          deep: "#EFE8D6", // subtle wells / hover
        },
        // Matte navy — replaces black for text and dark surfaces
        navy: {
          DEFAULT: "#1E2A44",
          700: "#2A395C",
          600: "#34466B",
          50: "#EAEDF3",
        },
        // Muted gold accents (strips, hairlines, highlights)
        gold: {
          DEFAULT: "#C2A14A",
          soft: "#DEC987",
          deep: "#A8862F",
        },
        // Sky blue — the student's own messages
        sky: {
          DEFAULT: "#D7EAF7",
          200: "#BFDDF1",
          700: "#2F6EA5",
        },
        ink: {
          DEFAULT: "#1E2A44", // primary text (navy)
          soft: "#56607A", // secondary text (slate)
        },
        line: "#E6DDC8", // warm hairline borders
      },
      fontFamily: {
        sans: ['"Inter"', "ui-sans-serif", "system-ui", "Segoe UI", "Arial", "sans-serif"],
        display: ['"Fraunces"', "Georgia", "Cambria", "Times New Roman", "serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(30,42,68,0.04), 0 8px 24px rgba(30,42,68,0.06)",
        lift: "0 12px 36px rgba(30,42,68,0.12)",
      },
      borderRadius: { xl2: "1.1rem" },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: { "0%": { backgroundPosition: "-200% 0" }, "100%": { backgroundPosition: "200% 0" } },
      },
      animation: {
        "fade-up": "fade-up 0.5s ease-out both",
        shimmer: "shimmer 2.2s linear infinite",
      },
    },
  },
  plugins: [],
};

export default config;
