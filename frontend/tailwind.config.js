export default {
  content: [
    "./index.html", 
    "./src/**/*.{js,ts,jsx,tsx}"
  ],

  theme: {
    extend: {

      colors: {
        base:      "var(--bg-base)",
        elevated:  "var(--bg-elevated)",
        card:      "var(--bg-card)",
        hover:     "var(--bg-hover)",
        border:    "var(--border)",
        accent:    "var(--accent)",
        primary:   "var(--text-primary)",
        secondary: "var(--text-secondary)",
        muted:     "var(--text-muted)",
      },

      fontFamily: {
        sans: [
          'Inter', 
          'system-ui', 
          'sans-serif'
        ],

        mono: [
          'JetBrains Mono', 
          'monospace'
        ],
      },

      borderColor: { 
        DEFAULT: "var(--border)" 
      },

      animation: {
        'fadeIn': 'fadeIn 0.25s ease forwards',
      },

    },
  },

  plugins: [],
};