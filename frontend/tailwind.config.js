/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // The Scribe design system — sacred + modern
        ink: {
          DEFAULT: '#0D0D0D',    // near-black warm background
          50:  '#F5F0E8',        // warm off-white primary text
          100: '#E8E2D8',
          200: '#C4BDB0',
          300: '#9A9088',
          400: '#7A7570',        // muted text
          500: '#5A5550',
          600: '#3A3530',
          700: '#2A2520',
          800: '#1E1E1E',        // card
          900: '#161616',        // surface
          950: '#0D0D0D',        // background
        },
        gold: {
          DEFAULT: '#C9A84C',    // warm gold accent
          50:  '#FDF8EC',
          100: '#F7EDCC',
          200: '#EFD98A',
          300: '#E0C05A',
          400: '#C9A84C',        // primary accent
          500: '#A8892E',
          600: '#7D6520',
          700: '#54431A',
          800: '#2A2318',        // gold-tint background for scripture blocks
          900: '#1A160D',
        },
        parchment: '#F5F0E8',
        muted: '#7A7570',
      },
      fontFamily: {
        display: ['"Cormorant Garamond"', 'Georgia', 'serif'],
        body: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      fontSize: {
        'display-2xl': ['4.5rem', { lineHeight: '1.1', letterSpacing: '-0.02em' }],
        'display-xl':  ['3.75rem', { lineHeight: '1.1', letterSpacing: '-0.02em' }],
        'display-lg':  ['3rem',    { lineHeight: '1.15', letterSpacing: '-0.01em' }],
        'display-md':  ['2.25rem', { lineHeight: '1.2',  letterSpacing: '-0.01em' }],
        'display-sm':  ['1.875rem',{ lineHeight: '1.25' }],
        'display-xs':  ['1.5rem',  { lineHeight: '1.3'  }],
      },
      backgroundImage: {
        'gold-gradient': 'linear-gradient(135deg, #C9A84C 0%, #E0C05A 50%, #C9A84C 100%)',
        'ink-gradient':  'linear-gradient(180deg, #161616 0%, #0D0D0D 100%)',
        'glow-gold':     'radial-gradient(ellipse at center, rgba(201,168,76,0.15) 0%, transparent 70%)',
      },
      boxShadow: {
        'gold-sm':  '0 0 0 1px rgba(201,168,76,0.3)',
        'gold-md':  '0 0 20px rgba(201,168,76,0.15)',
        'gold-lg':  '0 0 40px rgba(201,168,76,0.2)',
        'card':     '0 1px 3px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.6)',
        'card-hover': '0 4px 16px rgba(0,0,0,0.5), 0 0 0 1px rgba(201,168,76,0.2)',
      },
      animation: {
        'quill-draw': 'quillDraw 1.5s ease-out forwards',
        'fade-in-up': 'fadeInUp 0.4s ease-out',
        'pulse-gold': 'pulseGold 2s ease-in-out infinite',
        'shimmer':    'shimmer 1.5s infinite linear',
      },
      keyframes: {
        quillDraw: {
          '0%':   { strokeDashoffset: '100%', opacity: '0' },
          '30%':  { opacity: '1' },
          '100%': { strokeDashoffset: '0%', opacity: '1' },
        },
        fadeInUp: {
          '0%':   { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        pulseGold: {
          '0%, 100%': { opacity: '0.6' },
          '50%':      { opacity: '1' },
        },
        shimmer: {
          '0%':   { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
    },
  },
  plugins: [],
}
