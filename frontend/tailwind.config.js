/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // The Scribe — a study desk, not a dashboard.
        // Warm paper for reading/writing surfaces; deep study-room chrome.
        paper: {
          DEFAULT: '#F7F3EA',
          50:  '#FDFBF6',
          100: '#F7F3EA',
          200: '#EEE7D8',
          300: '#E0D6C0',
          400: '#C8BCA3',
        },
        study: {
          DEFAULT: '#2B2620',
          50:  '#EFEAE2',
          100: '#D8D0C3',
          200: '#A99C8A',
          300: '#7C7164',
          400: '#5A5246',
          500: '#433D34',
          600: '#36312A',
          700: '#2B2620',
          800: '#221E19',
          900: '#181512',
        },
        // Single accent: oxidized copper-red, like sealing wax / old binding cloth
        seal: {
          DEFAULT: '#A8462F',
          50:  '#F8E9E4',
          100: '#EFCCC1',
          200: '#DD9D89',
          300: '#C76E51',
          400: '#A8462F',
          500: '#8A3722',
          600: '#6B2A1A',
          700: '#4A1C12',
        },
        ink: '#2B2620',
      },
      fontFamily: {
        display: ['"Source Serif 4"', '"Source Serif Pro"', 'Georgia', 'serif'],
        body: ['"Source Sans 3"', '"Source Sans Pro"', 'system-ui', 'sans-serif'],
        manuscript: ['"Lora"', 'Georgia', 'serif'],
        mono: ['"IBM Plex Mono"', 'monospace'],
      },
      fontSize: {
        'display-2xl': ['3.75rem', { lineHeight: '1.08', letterSpacing: '-0.01em' }],
        'display-xl':  ['3rem',    { lineHeight: '1.1',  letterSpacing: '-0.01em' }],
        'display-lg':  ['2.375rem',{ lineHeight: '1.15' }],
        'display-md':  ['1.875rem',{ lineHeight: '1.2'  }],
        'display-sm':  ['1.5rem',  { lineHeight: '1.3'  }],
        'display-xs':  ['1.25rem', { lineHeight: '1.35' }],
      },
      backgroundImage: {
        'wax-gradient': 'linear-gradient(135deg, #A8462F 0%, #C76E51 100%)',
      },
      boxShadow: {
        'paper':       '0 1px 2px rgba(43,38,32,0.06), 0 1px 1px rgba(43,38,32,0.04)',
        'paper-lift':  '0 4px 16px rgba(43,38,32,0.10), 0 1px 3px rgba(43,38,32,0.08)',
        'study-card':  '0 1px 3px rgba(0,0,0,0.3)',
        'study-hover': '0 4px 12px rgba(0,0,0,0.35)',
        'focus-seal':  '0 0 0 2px rgba(168,70,47,0.35)',
      },
      animation: {
        'fade-in-up': 'fadeInUp 0.35s ease-out',
        'cursor-blink': 'cursorBlink 1s step-end infinite',
      },
      keyframes: {
        fadeInUp: {
          '0%':   { opacity: '0', transform: 'translateY(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        cursorBlink: {
          '0%, 50%':   { opacity: '1' },
          '50.01%, 100%': { opacity: '0' },
        },
      },
    },
  },
  plugins: [],
}
