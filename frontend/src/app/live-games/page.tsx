"use client";

import { useEffect, useState } from 'react';
import Link from 'next/link';

interface LiveGame {
  id: string;
  status: string;
  start_time: string;
  rounds: number;
  board_width: number;
  board_height: number;
  num_apples: number;
  models: Record<string, string>;
  model_ranks: Record<string, number>;
  current_state: {
    round_number: number;
    snake_positions: Record<string, number[][]>;
    alive: Record<string, boolean>;
    scores: Record<string, number>;
    apples: number[][];
    board_state: string;
  } | null;
}

export default function LiveGamesPage() {
  const [liveGames, setLiveGames] = useState<LiveGame[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentTime, setCurrentTime] = useState(new Date());

  // Fetch live games
  const fetchLiveGames = async () => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_FLASK_URL || 'http://127.0.0.1:5000';
      const response = await fetch(`${apiUrl}/api/games/live`);
      if (!response.ok) {
        throw new Error(`Failed to fetch live games: ${response.status} ${response.statusText}`);
      }
      const data = await response.json();
      setLiveGames(data.games || []);
      setError(null);
    } catch (err) {
      console.error('Error fetching live games:', err);
      setError(err instanceof Error ? err.message : 'Failed to load live games');
    } finally {
      setLoading(false);
    }
  };

  // Helper function to format duration
  const formatDuration = (startTime: string) => {
    const start = new Date(startTime);
    const diffMs = currentTime.getTime() - start.getTime();
    const diffSecs = Math.floor(diffMs / 1000);

    const hours = Math.floor(diffSecs / 3600);
    const minutes = Math.floor((diffSecs % 3600) / 60);
    const seconds = diffSecs % 60;

    if (hours > 0) {
      return `${hours}h ${minutes}m ${seconds}s`;
    } else if (minutes > 0) {
      return `${minutes}m ${seconds}s`;
    } else {
      return `${seconds}s`;
    }
  };

  // Poll for live games every 2 seconds
  useEffect(() => {
    fetchLiveGames();

    const interval = setInterval(() => {
      fetchLiveGames();
    }, 2000);

    return () => clearInterval(interval);
  }, []);

  // Update current time every second for duration counter
  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto py-12 px-4 sm:px-6 lg:px-8">
        <div className="text-center">
          <h1 className="text-3xl font-extrabold text-gray-900 sm:text-4xl mb-8">
            Live Games
          </h1>
          <p className="text-gray-500">Loading live games...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto py-12 px-4 sm:px-6 lg:px-8">
        <div className="text-center">
          <h1 className="text-3xl font-extrabold text-gray-900 sm:text-4xl mb-8">
            Live Games
          </h1>
          <p className="text-red-500">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white">
      {/* Header Section */}
      <div className="bg-gray-50 py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center">
            <h1 className="text-3xl font-extrabold text-gray-900 sm:text-4xl">
              🔴 Live Games
            </h1>
            <p className="mt-3 max-w-2xl mx-auto text-xl text-gray-500 sm:mt-4">
              Watch AI battles happening right now
            </p>
          </div>
        </div>
      </div>

      {/* Live Games Section */}
      <div className="max-w-7xl mx-auto py-12 px-4 sm:px-6 lg:px-8">
        {liveGames.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-gray-500 text-lg">No games currently in progress</p>
            <p className="text-gray-400 text-sm mt-2">Check back soon to watch live battles!</p>
          </div>
        ) : (
          <div className="flex flex-col">
            <div className="-my-2 overflow-x-auto sm:-mx-6 lg:-mx-8">
              <div className="py-2 align-middle inline-block min-w-full sm:px-6 lg:px-8">
                <div className="shadow overflow-hidden border-b border-gray-200 sm:rounded-lg">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Status
                        </th>
                        <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Models
                        </th>
                        <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Play Time
                        </th>
                        <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Current Round
                        </th>
                        <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Score
                        </th>
                        <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Actions
                        </th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {liveGames.map((game) => {
                        const currentRound = game.current_state?.round_number || 0;
                        const scores = game.current_state?.scores || {};
                        const models = game.models || {};
                        const modelRanks = game.model_ranks || {};
                        const playDuration = formatDuration(game.start_time);

                        return (
                          <tr key={game.id} className="hover:bg-gray-50">
                            <td className="px-6 py-4 whitespace-nowrap">
                              <span className="flex items-center">
                                <span className="h-2 w-2 rounded-full bg-red-500 animate-pulse mr-2"></span>
                                <span className="text-xs font-semibold text-red-600">LIVE</span>
                              </span>
                            </td>
                            <td className="px-6 py-4 text-sm text-gray-900">
                              {Object.entries(models).map(([id, modelName]) => {
                                const rank = modelRanks[id];
                                return (
                                  <div key={id}>
                                    <Link
                                      href={`/models/${encodeURIComponent(modelName)}`}
                                      className="text-indigo-600 hover:text-indigo-900 hover:underline"
                                    >
                                      {modelName.slice(0, 25)}
                                      {rank && ` (#${rank})`}
                                    </Link>
                                  </div>
                                );
                              })}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                              {playDuration}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 font-medium">
                              Round {currentRound}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                              {Object.entries(scores).map(([id, score], idx) => (
                                <span key={id}>
                                  {score}
                                  {idx < Object.keys(scores).length - 1 && ' - '}
                                </span>
                              ))}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                              <Link
                                href={`/live-games/${game.id}`}
                                className="text-indigo-600 hover:text-indigo-900"
                              >
                                Watch Live
                              </Link>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="mt-6 text-center">
          <p className="text-xs text-gray-400">
            Auto-refreshing every 2 seconds...
          </p>
        </div>
      </div>
    </div>
  );
}
