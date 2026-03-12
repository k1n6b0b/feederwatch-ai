/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        surface: {
          base: '#0f172a',   // slate-900 — page background
          card: '#1e293b',   // slate-800 — card background
          elevated: '#334155', // slate-700 — elevated surfaces, borders
        },
        accent: {
          DEFAULT: '#10b981', // emerald-500
          hover:   '#059669', // emerald-600
          muted:   '#065f46', // emerald-900 — subtle bg
        },
        status: {
          connected: '#10b981', // emerald-500
          degraded:  '#f59e0b', // amber-400
          error:     '#ef4444', // red-500
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
    },
  },
  plugins: [],
}
