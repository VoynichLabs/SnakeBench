import { ImageResponse } from 'next/og'
import { getOgFonts } from '@/lib/og'

export const runtime = 'edge'

export const alt = 'SnakeBench Matchup'
export const size = {
  width: 1200,
  height: 630,
}
export const contentType = 'image/png'

interface GameMetadata {
  models?: Record<string, string>
}

interface GameData {
  metadata?: GameMetadata
  players?: Record<string, { name?: string }>
}

export default async function Image({ params }: { params: { id: string } }) {
  const fonts = await getOgFonts()
  const { id } = params

  try {
    const gamesResponse = await fetch(`${process.env.FLASK_URL}/api/matches/${id}`, {
      next: { revalidate: 300 },
    })

    if (!gamesResponse.ok) {
      console.error(`[OG Image] Failed to fetch match data for ID ${id}. Status: ${gamesResponse.status}`)
      return buildFallbackImage(
        gamesResponse.status === 404 ? 'Match not found' : 'Match unavailable',
        fonts,
        gamesResponse.status === 404 ? 404 : 500
      )
    }

    let gameData: GameData | null = null
    try {
      gameData = (await gamesResponse.json()) as GameData
    } catch (err) {
      console.error(`[OG Image] JSON parse failed for match ${id}:`, err)
    }

    const metadataModels = gameData?.metadata?.models ?? {}
    const playerModels =
      Object.entries(gameData?.players ?? {}).reduce<Record<string, string>>((acc, [id, data]) => {
        const name = (data as { name?: string })?.name
        if (name) acc[id] = name
        return acc
      }, {}) ?? {}

    const mergedModels: Record<string, string> = { ...metadataModels, ...playerModels }
    const orderedIds = Object.keys(mergedModels).sort((a, b) => Number(a) - Number(b))
    const modelNames = orderedIds.map((id) => mergedModels[id]).filter(Boolean)

    const player1 = modelNames[0] || 'Model 1'
    const player2 = modelNames[1] || (modelNames[0] ? 'Opponent' : 'Model 2')

    return new ImageResponse(
      (
        <div
          style={{
            width: '100%',
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            gap: '28px',
            background:
              'radial-gradient(circle at 20% 20%, rgba(16, 185, 129, 0.12), transparent 32%), radial-gradient(circle at 80% 25%, rgba(99, 102, 241, 0.14), transparent 32%), linear-gradient(135deg, #0b1120 0%, #0f172a 55%, #0b1120 100%)',
            color: '#e5e7eb',
            boxSizing: 'border-box',
            padding: '48px 64px',
            fontFamily: '"Source Sans 3", "Press Start 2P", system-ui, sans-serif',
            letterSpacing: '-0.01em',
          }}
        >
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '14px',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                fontFamily: '"Press Start 2P", "Source Sans 3", system-ui, sans-serif',
                fontSize: 32,
                color: '#c7f9cc',
                letterSpacing: '-0.03em',
              }}
            >
              <span style={{ fontSize: 38 }}>🐍</span>
              <span>SnakeBench</span>
            </div>

            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                fontFamily: '"Press Start 2P", "Source Sans 3", system-ui, sans-serif',
                fontSize: 16,
                color: '#e5e7eb',
                textTransform: 'uppercase',
              }}
            >
              <span style={{ color: '#a5b4fc' }}>Matchup:</span>
              <span style={{ color: '#22c55e' }}>{player1}</span>
              <span style={{ color: '#e5e7eb' }}>vs</span>
              <span style={{ color: '#a855f7' }}>{player2}</span>
            </div>
          </div>

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '18px',
              width: '100%',
            }}
          >
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '10px',
                padding: '26px 22px',
                borderRadius: '16px',
                background: 'linear-gradient(145deg, #dcfce7, #bbf7d0)',
                color: '#0f172a',
                border: '2px solid #22c55e',
                width: '42%',
                minHeight: '170px',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  fontFamily: '"Press Start 2P", "Source Sans 3", system-ui, sans-serif',
                  fontSize: 13,
                  color: '#0f172a',
                  letterSpacing: '-0.02em',
                  textTransform: 'uppercase',
                }}
              >
                Player 1
              </div>
              <div
                style={{
                  display: 'flex',
                  fontFamily: '"Source Sans 3", "Press Start 2P", system-ui, sans-serif',
                  fontSize: 32,
                  fontWeight: 700,
                  lineHeight: 1.2,
                  wordBreak: 'break-word',
                }}
              >
                {player1}
              </div>
              <div
                style={{
                  display: 'flex',
                  fontFamily: '"Press Start 2P", "Source Sans 3", system-ui, sans-serif',
                  fontSize: 11,
                  color: 'rgba(15, 23, 42, 0.7)',
                  letterSpacing: '-0.01em',
                }}
              >
                Ready to battle
              </div>
            </div>

            <div
              style={{
                display: 'flex',
                width: '82px',
                height: '82px',
                borderRadius: '50%',
                border: '2px solid rgba(255, 255, 255, 0.55)',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#e5e7eb',
                fontFamily: '"Press Start 2P", "Source Sans 3", system-ui, sans-serif',
                fontSize: 18,
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
              }}
            >
              VS
            </div>

            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '10px',
                padding: '26px 22px',
                borderRadius: '16px',
                background: 'linear-gradient(145deg, #e0e7ff, #c7d2fe)',
                color: '#0f172a',
                border: '2px solid #6366f1',
                width: '42%',
                minHeight: '170px',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  fontFamily: '"Press Start 2P", "Source Sans 3", system-ui, sans-serif',
                  fontSize: 13,
                  color: '#0f172a',
                  letterSpacing: '-0.02em',
                  textTransform: 'uppercase',
                }}
              >
                Player 2
              </div>
              <div
                style={{
                  display: 'flex',
                  fontFamily: '"Source Sans 3", "Press Start 2P", system-ui, sans-serif',
                  fontSize: 32,
                  fontWeight: 700,
                  lineHeight: 1.2,
                  wordBreak: 'break-word',
                }}
              >
                {player2}
              </div>
              <div
                style={{
                  display: 'flex',
                  fontFamily: '"Press Start 2P", "Source Sans 3", system-ui, sans-serif',
                  fontSize: 11,
                  color: 'rgba(15, 23, 42, 0.7)',
                  letterSpacing: '-0.01em',
                }}
              >
                Ready to battle
              </div>
            </div>
          </div>

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              color: '#c7f9cc',
              fontFamily: '"Press Start 2P", "Source Sans 3", system-ui, sans-serif',
            }}
          >
            <span style={{ fontSize: 32 }}>🐍</span>
            <span style={{ fontSize: 18, letterSpacing: '-0.02em' }}>SnakeBench</span>
          </div>
        </div>
      ),
      {
        ...size,
        fonts: fonts.length ? fonts : undefined,
      }
    )
  } catch (error) {
    console.error(`[OG Image] Error generating image for ID ${id}:`, error)
    return buildFallbackImage('Server error', fonts, 500)
  }
}

function buildFallbackImage(
  message: string,
  fonts: Awaited<ReturnType<typeof getOgFonts>>,
  status?: number
) {
  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          gap: '28px',
          padding: '48px 64px',
          background: 'linear-gradient(135deg, #111827, #0b1120)',
          color: '#e5e7eb',
          fontFamily: '"Press Start 2P", "Source Sans 3", system-ui, sans-serif',
          boxSizing: 'border-box',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            color: '#c7f9cc',
          }}
        >
          <span style={{ fontSize: 30 }}>🐍</span>
          <span style={{ fontSize: 18 }}>SnakeBench</span>
        </div>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '24px 32px',
            borderRadius: '18px',
            border: '2px solid rgba(255,255,255,0.25)',
            background: 'rgba(255,255,255,0.04)',
            textAlign: 'center',
          }}
        >
          {message}
        </div>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            color: '#c7f9cc',
          }}
        >
          <span style={{ fontSize: 30 }}>🐍</span>
          <span style={{ fontSize: 18 }}>SnakeBench</span>
        </div>
      </div>
    ),
    {
      ...size,
      fonts: fonts.length ? fonts : undefined,
      status,
    }
  )
}
