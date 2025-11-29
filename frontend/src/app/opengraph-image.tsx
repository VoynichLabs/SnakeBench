import { ImageResponse } from 'next/og'
import { getOgFonts } from '@/lib/og'

export const runtime = 'edge'

export const alt = 'SnakeBench'
export const size = {
  width: 1200,
  height: 630,
}
export const contentType = 'image/png'

export default async function Image() {
  const fonts = await getOgFonts()

  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          position: 'relative',
          background: 'radial-gradient(circle at 20% 20%, rgba(16, 185, 129, 0.18), transparent 35%), radial-gradient(circle at 80% 30%, rgba(59, 130, 246, 0.18), transparent 35%), linear-gradient(135deg, #0b1120 0%, #111827 50%, #0f172a 100%)',
          color: '#f8fafc',
          boxSizing: 'border-box',
          padding: '64px',
          fontFamily: '"Press Start 2P", "Source Sans 3", system-ui, sans-serif',
        }}
      >
        <div
          style={{
            position: 'absolute',
            inset: '28px',
            border: '2px solid rgba(148, 163, 184, 0.25)',
            borderRadius: '24px',
            boxShadow: '0 30px 80px rgba(0, 0, 0, 0.35) inset, 0 12px 32px rgba(0, 0, 0, 0.35)',
          }}
        />

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '20px',
            fontSize: 44,
            letterSpacing: '-0.02em',
            textShadow: '0 8px 30px rgba(0, 0, 0, 0.35)',
          }}
        >
          <span style={{ fontSize: 54 }}>🐍</span>
          <span style={{ color: '#c7f9cc' }}>SnakeBench</span>
        </div>
      </div>
    ),
    {
      ...size,
      fonts: fonts.length ? fonts : undefined,
    }
  )
}
