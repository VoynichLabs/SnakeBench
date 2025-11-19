"use client";

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

interface GameState {
  id: string;
  status: string;
  start_time: string;
  rounds: number;
  board_width: number;
  board_height: number;
  num_apples: number;
  models: Record<string, string>;
  current_state: {
    round_number: number;
    snake_positions: Record<string, number[][]>;
    alive: Record<string, boolean>;
    scores: Record<string, number>;
    apples: number[][];
    board_state: string;
  } | null;
  total_score: number | null;
  total_cost: number | null;
}

export default function LiveGameViewerPage({ params }: { params: Promise<{ id: string }> }) {
  const [gameId, setGameId] = useState<string | null>(null);
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [duration, setDuration] = useState<string>('0:00');
  const router = useRouter();

  // Unwrap params
  useEffect(() => {
    params.then((p) => setGameId(p.id));
  }, [params]);

  // Fetch game state
  const fetchGameState = async (id: string) => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_FLASK_URL || 'http://127.0.0.1:5000';
      const response = await fetch(`${apiUrl}/api/games/${id}/live`);
      if (!response.ok) {
        if (response.status === 404) {
          throw new Error('Game not found');
        }
        throw new Error(`Failed to fetch game state: ${response.status} ${response.statusText}`);
      }
      const data = await response.json();
      setGameState(data);
      setError(null);

      // If game is completed, redirect to match page after 3 seconds
      if (data.status === 'completed') {
        setTimeout(() => {
          router.push(`/match/${id}`);
        }, 3000);
      }
    } catch (err) {
      console.error('Error fetching game state:', err);
      setError(err instanceof Error ? err.message : 'Failed to load game state');
    } finally {
      setLoading(false);
    }
  };

  // Poll for game state every 1 second
  useEffect(() => {
    if (!gameId) return;

    fetchGameState(gameId);

    const interval = setInterval(() => {
      fetchGameState(gameId);
    }, 1000);

    return () => clearInterval(interval);
  }, [gameId]);

  // Update duration counter every second
  useEffect(() => {
    if (!gameState || gameState.status === 'completed') return;

    const updateDuration = () => {
      const startTime = new Date(gameState.start_time).getTime();
      const now = Date.now();
      const diff = Math.floor((now - startTime) / 1000); // difference in seconds

      const minutes = Math.floor(diff / 60);
      const seconds = diff % 60;
      setDuration(`${minutes}:${seconds.toString().padStart(2, '0')}`);
    };

    updateDuration(); // Update immediately
    const interval = setInterval(updateDuration, 1000);

    return () => clearInterval(interval);
  }, [gameState]);

  if (loading || !gameId) {
    return (
      <div className="max-w-7xl mx-auto py-12 px-4 sm:px-6 lg:px-8">
        <div className="text-center">
          <p className="text-gray-500">Loading game...</p>
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

  const currentState = gameState.current_state;
  const isCompleted = gameState.status === 'completed';

  return (
    <div className="bg-white min-h-screen">
      {/* Header */}
      <div className="bg-gray-50 py-8 border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center">
                {!isCompleted && (
                  <span className="flex items-center mr-4">
                    <span className="h-3 w-3 rounded-full bg-red-500 animate-pulse mr-2"></span>
                    <span className="text-sm font-semibold text-red-600">LIVE</span>
                  </span>
                )}
                {isCompleted && (
                  <span className="flex items-center mr-4">
                    <span className="text-sm font-semibold text-gray-600">COMPLETED</span>
                  </span>
                )}
                <h1 className="text-2xl font-bold text-gray-900">
                  Game {gameId.slice(0, 8)}...
                </h1>
                {!isCompleted && (
                  <span className="ml-4 text-lg font-mono text-indigo-600">
                    {duration}
                  </span>
                )}
              </div>
              <p className="text-sm text-gray-500 mt-1">
                Started: {new Date(gameState.start_time).toISOString().replace('T', ' ').replace('Z', '')} (UTC)
              </p>
            </div>
            <Link
              href="/live-games"
              className="text-indigo-600 hover:text-indigo-900 text-sm font-medium"
            >
              ← Back to Live Games
            </Link>
          </div>
        </div>
      </div>

      {/* Main Game View */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Board Visualization */}
          <div className="lg:col-span-2">
            <div className="bg-gray-50 rounded-lg p-6 border border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Game Board</h2>
              {currentState ? (
                <pre className="font-mono text-xs overflow-x-auto bg-white p-4 rounded border border-gray-300 leading-relaxed">
                  {currentState.board_state}
                </pre>
              ) : (
                <p className="text-gray-500 text-center py-8">
                  {isCompleted ? 'Game completed - redirecting to replay...' : 'Waiting for game data...'}
                </p>
              )}
            </div>

            {/* Board Legend */}
            {currentState && (
              <div className="mt-4 bg-gray-50 rounded-lg p-4 border border-gray-200">
                <h3 className="text-sm font-semibold text-gray-900 mb-2">Legend</h3>
                <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                  <div><span className="font-bold">.</span> - Empty space</div>
                  <div><span className="font-bold">A</span> - Apple</div>
                  <div><span className="font-bold">0, 1, 2...</span> - Snake head (player number)</div>
                  <div><span className="font-bold">T</span> - Snake body/tail</div>
                </div>
              </div>
            )}
          </div>

          {/* Scores & Stats Sidebar */}
          <div className="space-y-6">
            {/* Scores */}
            <div className="bg-gray-50 rounded-lg p-6 border border-gray-200">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-gray-900">Scores</h2>
                <span className="text-sm text-gray-600">Round {currentState?.round_number || 0}</span>
              </div>
              {currentState && currentState.scores ? (
                <div className="space-y-3">
                  {Object.entries(currentState.scores).map(([playerId, score]) => {
                    const isAlive = currentState.alive[playerId];
                    const modelName = gameState.models?.[playerId] || `Player ${playerId}`;
                    return (
                      <div key={playerId} className="flex items-center justify-between">
                        <div className="flex items-center">
                          <span className={`h-2 w-2 rounded-full mr-2 ${isAlive ? 'bg-green-500' : 'bg-gray-400'}`}></span>
                          <span className="font-medium text-gray-900">{modelName}</span>
                        </div>
                        <span className="text-2xl font-bold text-gray-900">{score}</span>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="text-gray-500 text-sm">No scores available</p>
              )}
            </div>

            {/* Snake Positions */}
            <div className="bg-gray-50 rounded-lg p-6 border border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Snake Info</h2>
              {currentState && currentState.snake_positions ? (
                <div className="space-y-4">
                  {Object.entries(currentState.snake_positions).map(([playerId, positions]) => {
                    const isAlive = currentState.alive[playerId];
                    const modelName = gameState.models?.[playerId] || `Player ${playerId}`;
                    return (
                      <div key={playerId}>
                        <div className="flex items-center justify-between mb-1">
                          <span className="font-medium text-gray-900">{modelName}</span>
                          <span className={`text-xs font-semibold ${isAlive ? 'text-green-600' : 'text-red-600'}`}>
                            {isAlive ? 'ALIVE' : 'DEAD'}
                          </span>
                        </div>
                        <div className="text-xs text-gray-600 space-y-0.5">
                          <div>Head: ({positions[0]?.[0]}, {positions[0]?.[1]})</div>
                          <div>Length: {positions.length}</div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="text-gray-500 text-sm">No snake data available</p>
              )}
            </div>

            {/* Auto-refresh indicator */}
            {!isCompleted && (
              <div className="text-center">
                <p className="text-xs text-gray-400">
                  Auto-refreshing every 1 second...
                </p>
              </div>
            )}

            {/* Completed message */}
            {isCompleted && (
              <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
                <p className="text-sm text-blue-800 text-center">
                  Game completed! Redirecting to full replay in 3 seconds...
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
