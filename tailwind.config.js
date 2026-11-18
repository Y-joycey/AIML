/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        blush: '#FCE7F3',
        mint: '#DCFCE7',
        sky: '#E0F2FE',
        peach: '#FFEDD5',
        lilac: '#EDE9FE',
        cream: '#FFF7ED',
        slate: '#F8FAFC',
      },
      boxShadow: {
        soft: '0 10px 30px rgba(15, 23, 42, 0.08)',
      },
    },
  },
  plugins: [],
};
