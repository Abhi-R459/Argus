/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Segoe UI Variable', 'Segoe UI', '-apple-system', 'BlinkMacSystemFont', 'Roboto', 'sans-serif'],
        mono: ['Cascadia Code', 'Cascadia Mono', 'Consolas', 'SFMono-Regular', 'Menlo', 'monospace'],
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
      boxShadow: {
        '2xs': '0 1px 2px rgba(16, 24, 40, 0.05)',
        'xs': '0 1px 3px rgba(16, 24, 40, 0.08), 0 1px 2px rgba(16, 24, 40, 0.04)',
      },
      spacing: {
        '0.2': '0.05rem',
        '4.5': '1.125rem',
        '9.5': '2.375rem',
      },
      backdropBlur: {
        xs: '2px',
      },
      keyframes: {
        modalEnter: {
          '0%': { transform: 'scale(0.95)', opacity: '0' },
          '100%': { transform: 'scale(1)', opacity: '1' },
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
        'fade-cascade': 'fadeCascade 220ms cubic-bezier(0.23, 1, 0.32, 1) forwards',
        'fast-spin': 'fastSpin 0.6s linear infinite',
      },
      colors: {
        slate: {
          50: '#f4f4f4',
          100: '#e8e8e8',
          200: '#d1d1d1',
          300: '#bdbdbd',
          400: '#8d8d8d',
          500: '#6f6f6f',
          600: '#525252',
          700: '#393939',
          800: '#262626',
          850: '#1d1d1d',
          900: '#161616',
          925: '#111111',
          950: '#0f0f0f',
        },
        portal: {
          canvas: '#f4f4f4',
          surface: {
            1: '#ffffff',
            2: '#f4f4f4',
            3: '#e0e0e0',
          },
          hairline: {
            DEFAULT: '#e0e0e0',
            strong: '#c6c6c6',
          },
          ink: {
            DEFAULT: '#161616',
            muted: '#525252',
            subtle: '#6f6f6f',
          },
          primary: {
            DEFAULT: '#0f62fe',
            hover: '#0043ce',
            focus: '#002d9c',
          },
          success: '#198038',
          warning: '#8e6a00',
          danger: '#da1e28',
          info: '#0043ce',
        },
        linear: {
          canvas: '#161616',
          surface: {
            DEFAULT: '#262626',
            1: '#262626',
            2: '#333333',
            3: '#393939',
            4: '#525252',
          },
          hairline: {
            DEFAULT: '#393939',
            strong: '#525252',
            tertiary: '#6f6f6f',
          },
          ink: {
            DEFAULT: '#f4f4f4',
            secondary: '#c6c6c6',
            muted: '#c6c6c6',
            subtle: '#a8a8a8',
            tertiary: '#8d8d8d',
          },
          primary: {
            DEFAULT: '#78a9ff',
            hover: '#a6c8ff',
            focus: '#4589ff',
          },
          secure: '#a6c8ff',
          success: '#6fdc8c',
          warning: '#f1c21b',
          danger: '#ff8389',
          info: '#78a9ff',
        },
        status: {
          warning: {
            DEFAULT: '#8e6a00',
            hover: '#755700',
            pressed: '#5e4600',
            subtle: 'rgba(142, 106, 0, 0.10)',
            border: 'rgba(142, 106, 0, 0.30)',
          },
        },
      },
    },
  },
  plugins: [],
}

