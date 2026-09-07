/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ["'IBM Plex Sans'", 'system-ui', 'sans-serif'],
        mono: ["'IBM Plex Mono'", 'monospace'],
      },
      colors: {
        pe: {
          teal: {
            50:  '#e9f6f0',
            100: '#cfe9e1',
            400: '#3dd7b8',
            500: '#12a594',
            600: '#0e9384',
            700: '#0b7a6e',
          },
          orange: {
            text:   '#b8410e',
            dot:    '#e8590c',
            bg:     '#fdeee6',
            border: '#f6d4c2',
          },
          amber: {
            text:   '#9a6b00',
            dot:    '#e0a400',
            bg:     '#fdf6e3',
            border: '#f0e4b8',
          },
          gray: {
            50:  '#f5f6f7',
            75:  '#fafbfb',
            100: '#f0f1f2',
            150: '#eceeef',
            200: '#e6e8e8',
            300: '#e0e3e3',
            400: '#d4d8d8',
            500: '#c4caca',
            600: '#a4abab',
            700: '#8a9090',
            800: '#5c6363',
            850: '#3a4040',
            900: '#1a1d1d',
          },
        },
      },
      animation: {
        'pe-spin': 'pe-spin .7s linear infinite',
        'pe-fade': 'pe-fade .25s ease',
      },
      keyframes: {
        'pe-spin': { to: { transform: 'rotate(360deg)' } },
        'pe-fade': {
          from: { opacity: '0', transform: 'translateY(4px)' },
          to:   { opacity: '1', transform: 'none' },
        },
      },
    },
  },
  plugins: [],
}
