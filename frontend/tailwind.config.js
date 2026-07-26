/**
 * Design tokens — industrial control-room HMI.
 *
 * The reference is a DCS operator console (Honeywell Experion / TDC style),
 * not a web dashboard: alarm colours follow ISA-18.2 convention, panels are
 * hairline-bordered instrument bezels with near-square corners, and every
 * process value is monospaced.
 *
 * One token per concept, used identically everywhere. A CRITICAL alarm banner,
 * a CRITICAL table cell and a CRITICAL chart stroke all read `alarm.critical`.
 *
 * @type {import('tailwindcss').Config}
 */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // ── Console surfaces ────────────────────────────────────────────────
        // Near-black with a slight blue-grey cast. Panels sit one step lighter
        // and are separated by hairlines rather than shadows, so the screen
        // reads as bezelled instruments bolted to a console face.
        hmi: {
          void: '#0A0E14', // console background
          panel: '#12181F', // panel face
          header: '#171E27', // panel header strip / table header
          inset: '#0D1218', // recessed wells (chart plot, inputs)
          line: '#1F2937', // hairline border
          bezel: '#2B3644', // emphasised edge / hover border
          text: '#E8EDF2', // primary readout text
          label: '#8A97A6', // secondary + uppercase labels (cool grey)
          dim: '#5B6672', // captions, axis ticks, tag suffixes
        },

        // ── Alarm scale (ISA-18.2) ──────────────────────────────────────────
        // Red = critical, orange = high, yellow = caution (used sparingly),
        // teal = normal. Desaturated enough not to vibrate on a projector.
        alarm: {
          critical: '#E5484D',
          'critical-fill': '#2A1114', // banner/badge wash
          high: '#F5A524',
          'high-fill': '#2A1D08',
          medium: '#F5D90A',
          'medium-fill': '#26220A',
          normal: '#2DD4BF',
          'normal-fill': '#0C2422',
        },

        // ── Single interactive signal ───────────────────────────────────────
        // Same teal as the NORMAL alarm state: active nav, slider, acknowledge
        // control, focus ring. Nothing else in the app is allowed an accent.
        signal: {
          DEFAULT: '#2DD4BF',
          bright: '#5EEAD4',
          fill: '#0C2422',
        },

        // ── Trend pens ──────────────────────────────────────────────────────
        // Saturated recorder-pen colours, one fixed pen per instrument tag, so
        // ST.PV is the same amber on every trend in the app.
        pen: {
          blue: '#38BDF8', // BW.PV — basis weight
          green: '#34D399', // BW.SP — target / setpoint
          violet: '#A78BFA', // BW.DEV — deviation
          cyan: '#22D3EE', // MOI.PV — moisture
          amber: '#F5A524', // ST.PV — steam pressure
          magenta: '#F472B6', // SF.PV — stock flow
          steel: '#94A3B8', // MS.PV — machine speed
          teal: '#2DD4BF', // FF.PV — filler flow
          limit: '#E5484D', // specification limits
        },
      },

      fontFamily: {
        // Prose and uppercase panel labels only.
        sans: ['IBM Plex Sans', 'Inter', 'system-ui', '-apple-system', 'sans-serif'],
        // Every process value, tag id, setpoint and timestamp.
        mono: ['IBM Plex Mono', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },

      fontSize: {
        // Console type scale. Labels are small, uppercase and letter-spaced,
        // the way real HMI screens annotate a faceplate.
        screen: ['1.125rem', { lineHeight: '1.2', fontWeight: '600', letterSpacing: '0.02em' }],
        panel: ['0.8125rem', { lineHeight: '1.25', fontWeight: '600', letterSpacing: '0.09em' }],
        tag: ['0.6875rem', { lineHeight: '1.2', fontWeight: '500', letterSpacing: '0.12em' }],
        micro: ['0.625rem', { lineHeight: '1.25', letterSpacing: '0.1em' }],
        body: ['0.8125rem', { lineHeight: '1.55' }],
        caption: ['0.75rem', { lineHeight: '1.45' }],
        // Digit readouts, largest first.
        pv: ['2rem', { lineHeight: '1', fontWeight: '600', letterSpacing: '-0.02em' }],
        'pv-sm': ['1.375rem', { lineHeight: '1.05', fontWeight: '600', letterSpacing: '-0.01em' }],
        'pv-xs': ['1rem', { lineHeight: '1.1', fontWeight: '600' }],
        banner: ['1.75rem', { lineHeight: '1', fontWeight: '700', letterSpacing: '0.04em' }],
      },

      borderRadius: {
        // Instruments do not have 16px corners.
        panel: '2px',
        control: '2px',
      },

      maxWidth: {
        shell: '1680px',
        cell: '22rem',
      },

      keyframes: {
        // The one animated moment: the recorder pen tip at the NOW scan line.
        'pen-tip': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.35' },
        },
        'fade-in': {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
      },

      animation: {
        'pen-tip': 'pen-tip 1.6s steps(2, end) infinite',
        'fade-in': 'fade-in 0.15s ease-out both',
      },

    },
  },
  plugins: [],
};
