/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: '#10b981',
        secondary: '#3b82f6',
        background: '#ffffff',
        'background-light': '#f9fafb',
        text: '#1f2937',
        border: '#e5e7eb',
        alert: '#ef4444',
      },
    },
  },
  plugins: [],
}
