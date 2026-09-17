/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'Menlo', 'Monaco', 'Courier New', 'monospace'],
      },
      transitionTimingFunction: {
        'emil-out': 'cubic-bezier(0.23, 1, 0.32, 1)',
        'emil-in-out': 'cubic-bezier(0.77, 0, 0.175, 1)',
        'emil-drawer': 'cubic-bezier(0.32, 0.72, 0, 1)',
      },
      transitionDuration: {
        '160': '160ms',
        '240': '240ms',
        '280': '280ms',
      },
      keyframes: {
        modalEnter: {
          '0%': { transform: 'scale(0.95)', opacity: '0' },
          '100%': { transform: 'scale(1)', opacity: '1' },
        },
        drawerSlideIn: {
          '0%': { transform: 'translateX(100%)' },
          '100%': { transform: 'translateX(0)' },
        },
        drawerSlideOut: {
          '0%': { transform: 'translateX(0)' },
          '100%': { transform: 'translateX(100%)' },
        },
        fadeCascade: {
          '0%': { transform: 'translateY(6px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        fastSpin: {
          '0%': { transform: 'rotate(0deg)' },
          '100%': { transform: 'rotate(360deg)' },
        },
      },
      animation: {
        'modal-enter': 'modalEnter 180ms cubic-bezier(0.23, 1, 0.32, 1) forwards',
        'drawer-in': 'drawerSlideIn 280ms cubic-bezier(0.32, 0.72, 0, 1) forwards',
        'drawer-out': 'drawerSlideOut 200ms cubic-bezier(0.23, 1, 0.32, 1) forwards',
        'fade-cascade': 'fadeCascade 220ms cubic-bezier(0.23, 1, 0.32, 1) forwards',
        'fast-spin': 'fastSpin 0.6s linear infinite',
      },
      colors: {
        slate: {
          850: '#151e2e',
          925: '#0b1120',
        },
      },
    },
  },
  plugins: [],
}

