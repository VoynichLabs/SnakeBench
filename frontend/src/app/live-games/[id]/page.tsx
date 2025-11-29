"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import GameViewer, { BoardInfo, MoveEntry, NormalizedFrame, Position } from '@/components/match/GameViewer';
import MatchInfo from '@/components/match/MatchInfo';

interface LiveFramePayload {
  round_number?: number;
  snake_positions?: Record<string, number[][]>;
  alive?: Record<string, boolean>;
  scores?: Record<string, number>;
  apples?: number[][];
  board_state?: string;
  move_history?: Record<string, MoveEntry>[];
  last_move_time?: number;
}

interface LiveGameState {
  id: string;
  status: string;
  start_time: string | null;
  rounds: number;
  board_width: number;
  board_height: number;
  num_apples: number;
  models: Record<string, string>;
  model_ranks?: Record<string, number>;
  current_state: LiveFramePayload | null;
  total_score: number | null;
  total_cost: number | null;
}

function formatDuration(startTime: string | null | undefined, nowMs: number) {
  if (!startTime) return '—';
  const start = new Date(startTime).getTime();
  if (Number.isNaN(start)) return '—';
  const diff = Math.max(0, Math.floor((nowMs - start) / 1000));
  const minutes = Math.floor(diff / 60);
  const seconds = diff % 60;
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

function formatAgo(lastUpdate: number | null, nowMs: number) {
  if (!lastUpdate) return 'waiting...';
  const diff = Math.max(0, Math.floor((nowMs - lastUpdate) / 1000));
  if (diff < 60) return `${diff}s ago`;
  const minutes = Math.floor(diff / 60);
  const seconds = diff % 60;
  return `${minutes}m ${seconds}s ago`;
}

function StatCard({ label, value, tone = 'normal' }: { label: string; value: ReactNode; tone?: 'normal' | 'warn' | 'error' }) {
  const toneStyles = {
    normal: 'bg-gray-50 text-gray-800 border-gray-100',
    warn: 'bg-amber-50 text-amber-800 border-amber-100',
    error: 'bg-red-50 text-red-800 border-red-100',
  }[tone];

  return (
    <div className={`rounded-lg border px-3 py-2 ${toneStyles}`}>
      <p className="text-[10px] uppercase tracking-wide text-gray-500">{label}</p>
      <div className="text-sm font-semibold leading-tight">{value}</div>
    </div>
  );
}

export default function LiveGameViewerPage({ params }: { params: Promise<{ id: string }> }) {
  const [gameId, setGameId] = useState<string | null>(null);
  const [gameState, setGameState] = useState<LiveGameState | null>(null);
  const [frames, setFrames] = useState<NormalizedFrame[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<number | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const latestRoundRef = useRef<number>(-1);
  const router = useRouter();

  // Unwrap params
  useEffect(() => {
    params.then((p) => setGameId(p.id));
  }, [params]);

  // Heartbeat for timers
  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(interval);
  }, []);

  const normalizeFrame = useCallback((state: LiveFramePayload): NormalizedFrame => {
    const snakes: Record<string, Position[]> = {};
    Object.entries(state.snake_positions || {}).forEach(([id, coords]) => {
      snakes[id] = (coords || []).map((pair) => [pair[0], pair[1]] as Position);
    });

    const moves = Array.isArray(state.move_history)
      ? state.move_history[state.move_history.length - 1] as Record<string, MoveEntry> | undefined
      : undefined;

    return {
      round: typeof state.round_number === 'number' ? state.round_number : 0,
      state: {
        snakes,
        apples: (state.apples || []).map((pair) => [pair[0], pair[1]] as Position),
        alive: state.alive || {},
        scores: state.scores || {},
      },
      moves,
    };
  }, []);

  // Fetch game state
  const fetchGameState = useCallback(async (id: string) => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_FLASK_URL || 'http://127.0.0.1:5000';
      const response = await fetch(`${apiUrl}/api/games/${id}/live`);
      if (!response.ok) {
        if (response.status === 404) {
          throw new Error('Game not found');
        }
        throw new Error(`Failed to fetch game state: ${response.status} ${response.statusText}`);
      }
      const data: LiveGameState = await response.json();
      setGameState(data);
      setError(null);
      const nowTs = Date.now();
      let changeDetected = false;

      if (data.current_state) {
        const frame = normalizeFrame(data.current_state);
        setFrames((prev) => {
          const existingIndex = prev.findIndex((entry) => entry.round === frame.round);
          if (existingIndex !== -1) {
            const existing = prev[existingIndex];
            const sameState = JSON.stringify(existing.state) === JSON.stringify(frame.state);
            const sameMoves = JSON.stringify(existing.moves) === JSON.stringify(frame.moves);
            if (sameState && sameMoves) return prev;
            const updated = [...prev];
            updated[existingIndex] = frame;
            changeDetected = true;
            return updated;
          }
          const updated = [...prev, frame].sort((a, b) => a.round - b.round);
          changeDetected = true;
          return updated;
        });

        const newestRound = frame.round ?? latestRoundRef.current;
        latestRoundRef.current = newestRound;
      }

      // Use server-provided last_move_time if available, otherwise fall back to client timestamp
      const serverMoveTime = data.current_state?.last_move_time;
      if (serverMoveTime) {
        // Convert Unix timestamp (seconds) to milliseconds
        setLastUpdate(serverMoveTime * 1000);
      } else if (changeDetected) {
        // Fallback: use client timestamp when change detected but no server time
        setLastUpdate(nowTs);
      }

      // If game is completed, redirect to match page after replay processes
      if (data.status === 'completed') {
        setTimeout(() => router.push(`/match/${id}`), 2500);
      }
    } catch (err) {
      console.error('Error fetching game state:', err);
      setError(err instanceof Error ? err.message : 'Failed to load game state');
    } finally {
      setLoading(false);
    }
  }, [normalizeFrame, router]);

  // Poll for game state
  useEffect(() => {
    if (!gameId) return;

    fetchGameState(gameId);
    const interval = setInterval(() => {
      fetchGameState(gameId);
    }, 1200);

    return () => clearInterval(interval);
  }, [gameId, fetchGameState]);

  useEffect(() => {
    if (!frames.length) return;
    const latest = frames[frames.length - 1]?.round ?? -1;
    latestRoundRef.current = latest;
  }, [frames]);

  const models = useMemo(() => gameState?.models || {}, [gameState?.models]);
  const isCompleted = gameState?.status === 'completed';
  const board: BoardInfo | null = gameState ? {
    width: gameState.board_width,
    height: gameState.board_height,
    num_apples: gameState.num_apples,
  } : null;

  const modelIds = useMemo(() => {
    const ids = Object.keys(models);
    return ids.sort((a, b) => Number(a) - Number(b));
  }, [models]);
  const modelNames = useMemo(
    () => modelIds.map((id) => models?.[id] || `Player ${id}`),
    [modelIds, models]
  );

  const duration = formatDuration(gameState?.start_time, now);
  const sinceUpdateLabel = formatAgo(lastUpdate, now);

  const latestFrame = frames[frames.length - 1];
  const latestRound = latestFrame?.round ?? gameState?.current_state?.round_number ?? 0;

  const startTime = gameState?.start_time ? new Date(gameState.start_time) : null;
  const formattedDate = startTime
    ? startTime.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
    : 'Unknown date';
  const formattedTime = startTime
    ? startTime.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : 'Unknown time';

  if (loading || !gameId) {
    return (
      <div className="max-w-7xl mx-auto py-12 px-4 sm:px-6 lg:px-8">
        <div className="text-center">
          <p className="text-gray-500">Loading live game...</p>
        </div>
      </div>
    );
  }

  if (error || !gameState) {
    return (
      <div className="max-w-7xl mx-auto py-12 px-4 sm:px-6 lg:px-8">
        <div className="text-center">
          <h1 className="text-3xl font-extrabold text-gray-900 sm:text-4xl mb-8">
            Game Not Found
          </h1>
          <p className="text-red-500 mb-4">{error || 'Game not found'}</p>
          <Link href="/live-games" className="text-indigo-600 hover:text-indigo-900">
            Back to Live Games
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white min-h-screen">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="flex items-center px-3 py-1 rounded-full bg-red-50 border border-red-100">
              <span className={`h-2 w-2 rounded-full mr-2 ${isCompleted ? 'bg-gray-400' : 'bg-red-500 animate-pulse'}`} />
              <span className="text-xs font-semibold text-red-700">
                {isCompleted ? 'Completed' : 'Live'}
              </span>
            </span>
            <div className="text-sm text-gray-600 font-mono">
              Game {gameId.slice(0, 8)}...
            </div>
          </div>
          <Link
            href="/live-games"
            className="text-indigo-600 hover:text-indigo-900 text-sm font-medium"
          >
            ← Back to Live Games
          </Link>
        </div>

        <div className="mt-4">
          <MatchInfo modelNames={modelNames} date={formattedDate} time={formattedTime} />
        </div>

        <div className="mt-4 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          <StatCard label="Live for" value={duration} />
          <StatCard label="Last response" value={sinceUpdateLabel} />
          <StatCard label="Current round" value={latestRound} />
          <StatCard label="Board" value={`${gameState.board_width}×${gameState.board_height} • ${gameState.num_apples} apples`} />
          <StatCard
            label="Status"
            value={isCompleted ? 'Finished - building replay' : 'Streaming moves'}
            tone={isCompleted ? 'warn' : 'normal'}
          />
        </div>

        <div className="mt-6">
          {board && frames.length > 0 ? (
            <GameViewer
              frames={frames}
              board={board}
              modelIds={modelIds}
              modelNames={modelNames}
              gameId={gameId}
              liveMode
            />
          ) : (
            <div className="rounded-lg border border-dashed border-gray-200 bg-gray-50 p-6 text-center text-sm text-gray-600">
              <p className="font-medium">Waiting for the first live frame...</p>
              {gameState.current_state?.board_state && (
                <pre className="mt-4 font-mono text-[11px] overflow-x-auto bg-white p-4 rounded border border-gray-200 text-left">
                  {gameState.current_state.board_state}
                </pre>
              )}
            </div>
          )}
        </div>

        {isCompleted && (
          <div className="mt-4 bg-blue-50 rounded-lg p-4 border border-blue-200 text-blue-800 text-sm">
            Game finished. Redirecting to the full replay once it is ready...
          </div>
        )}
      </div>
    </div>
  );
}
