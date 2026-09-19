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
          850: '#151e2e',
          925: '#0b1120',
        },
        portal: {
          canvas: '#f8fafc',
          surface: {
            1: '#ffffff',
            2: '#f1f5f9',
            3: '#e2e8f0',
          },
          hairline: {
            DEFAULT: '#e2e8f0',
            strong: '#cbd5e1',
          },
          ink: {
            DEFAULT: '#0f172a',
            muted: '#475569',
            subtle: '#64748b',
          },
          primary: {
            DEFAULT: '#0f172a',
            hover: '#1e293b',
            focus: '#020617',
          },
          success: '#15803d',
          warning: '#b45309',
          danger: '#be123c',
          info: '#1d4ed8',
        },
        linear: {
          canvas: '#010102',
          surface: {
            1: '#0f1011',
            2: '#141516',
            3: '#18191a',
            4: '#191a1b',
          },
          hairline: {
            DEFAULT: '#23252a',
            strong: '#34343a',
            tertiary: '#3e3e44',
          },
          ink: {
            DEFAULT: '#f7f8f8',
            secondary: '#8a8f98',
            muted: '#d0d6e0',
            subtle: '#8a8f98',
            tertiary: '#62666d',
          },
          primary: {
            DEFAULT: '#5e6ad2',
            hover: '#4f5ac2',
            focus: '#5e69d1',
          },
          secure: '#7a7fad',
          success: '#27a644',
        },
        grafana: {
          orange: {
            DEFAULT: '#ff671d',
            hover: '#ff7e3e',
            pressed: '#e0530e',
            subtle: 'rgba(255, 103, 29, 0.12)',
            border: 'rgba(255, 103, 29, 0.35)',
          },
          blue: {
            DEFAULT: '#1b55f5',
            hover: '#3b6ff7',
            subtle: 'rgba(27, 85, 245, 0.12)',
            border: 'rgba(27, 85, 245, 0.35)',
          },
          neutral: {
            DEFAULT: '#67677e',
            subtle: '#8c8ca1',
            border: '#d8d8df',
          },
          surface: '#f4f4f6',
          border: '#e6e6ea',
        },
      },
    },
  },
  plugins: [],
}

