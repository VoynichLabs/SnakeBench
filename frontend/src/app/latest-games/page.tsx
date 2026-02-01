import Link from 'next/link';

// Force dynamic rendering - data changes frequently
export const dynamic = 'force-dynamic';

interface Participant {
  model_name: string;
  provider: string | null;
  player_slot: number;
  score: number;
  result: 'won' | 'lost' | 'tied';
  death_round: number | null;
  death_reason: string | null;
}

interface Game {
  game_id: string;
  start_time: string;
  end_time: string | null;
  rounds: number;
  replay_url: string;
  board_width: number;
  board_height: number;
  total_score: number;
  total_cost: number;
  participants: Participant[];
}

/**
 * Format a timestamp as relative time (e.g., "5 minutes ago", "2 days ago")
 * for times within the last 7 days, or as an absolute date (e.g., "November 28, 2024")
 * for older times.
 */
function formatRelativeTime(timestamp: string): string {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);

  // If within the last 7 days, show relative time
  if (diffDays < 7) {
    if (diffSeconds < 60) {
      return diffSeconds === 1 ? '1 second ago' : `${diffSeconds} seconds ago`;
    } else if (diffMinutes < 60) {
      return diffMinutes === 1 ? '1 minute ago' : `${diffMinutes} minutes ago`;
    } else if (diffHours < 24) {
      return diffHours === 1 ? '1 hour ago' : `${diffHours} hours ago`;
    } else {
      return diffDays === 1 ? '1 day ago' : `${diffDays} days ago`;
    }
  }

  // For older dates, show absolute date (e.g., "November 28, 2024")
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  });
}

async function getLatestGames(): Promise<Game[]> {
  try {
    const response = await fetch(
      `${process.env.FLASK_URL}/api/games?limit=100&sort_by=start_time`,
      { next: { revalidate: 60 } }
    );

    if (!response.ok) {
      throw new Error('Failed to fetch games');
    }

    const data = await response.json();
    return data.games || [];
  } catch (err) {
    console.error('[LatestGames] Error fetching data:', err);
    return [];
  }
}

export default async function LatestGamesPage() {
  const games = await getLatestGames();

  return (
    <div className="max-w-7xl mx-auto py-4 px-4">
      <div className="bg-white border border-gray-200">
        {/* Header */}
        <div className="px-3 py-2 border-b border-gray-200 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/" className="text-xs font-mono text-gray-400 hover:text-blue-600">
              &larr;
            </Link>
            <h1 className="text-lg font-mono font-bold text-gray-900">
              Latest Games
            </h1>
          </div>
          <div className="text-xs font-mono text-gray-500">
            <span className="text-gray-900 font-medium">{games.length}</span> recent matches
          </div>
        </div>

        {/* Games Table */}
        {games.length === 0 ? (
          <div className="p-4 text-sm font-mono text-gray-500">
            No games found.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="pl-6 pr-2 py-1.5 text-left text-[10px] font-mono text-gray-500 uppercase tracking-wider">Player 1</th>
                  <th className="px-2 py-1.5 text-left text-[10px] font-mono text-gray-500 uppercase tracking-wider">Player 2</th>
                  <th className="px-2 py-1.5 text-left text-[10px] font-mono text-gray-500 uppercase tracking-wider">Score</th>
                  <th className="px-2 py-1.5 text-left text-[10px] font-mono text-gray-500 uppercase tracking-wider">Played</th>
                  <th className="px-2 py-1.5 text-left text-[10px] font-mono text-gray-500 uppercase tracking-wider"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {games.map((game) => {
                  // Get the two participants
                  const player1 = game.participants.find(p => p.player_slot === 0);
                  const player2 = game.participants.find(p => p.player_slot === 1);

                  // Determine winner for styling
                  const player1Won = player1?.result === 'won';
                  const player2Won = player2?.result === 'won';
                  const isTie = player1?.result === 'tied';

                  return (
                    <tr key={game.game_id} className="hover:bg-blue-50 transition-colors">
                      <td className="pl-6 pr-2 py-1.5 whitespace-nowrap">
                        {player1 ? (
                          <Link
                            href={`/models/${encodeURIComponent(player1.model_name)}`}
                            className={`text-xs font-mono hover:text-blue-600 hover:underline ${
                              player1Won ? 'text-green-700 font-medium' : 'text-gray-900'
                            }`}
                          >
                            {player1.model_name}
                            {player1Won && <span className="ml-1 text-green-600">W</span>}
                            {isTie && <span className="ml-1 text-gray-400">T</span>}
                          </Link>
                        ) : (
                          <span className="text-xs font-mono text-gray-400">Unknown</span>
                        )}
                      </td>
                      <td className="px-2 py-1.5 whitespace-nowrap">
                        {player2 ? (
                          <Link
                            href={`/models/${encodeURIComponent(player2.model_name)}`}
                            className={`text-xs font-mono hover:text-blue-600 hover:underline ${
                              player2Won ? 'text-green-700 font-medium' : 'text-gray-900'
                            }`}
                          >
                            {player2.model_name}
                            {player2Won && <span className="ml-1 text-green-600">W</span>}
                            {isTie && <span className="ml-1 text-gray-400">T</span>}
                          </Link>
                        ) : (
                          <span className="text-xs font-mono text-gray-400">Unknown</span>
                        )}
                      </td>
                      <td className="px-2 py-1.5 whitespace-nowrap text-xs font-mono text-gray-600">
                        {player1?.score ?? 0} - {player2?.score ?? 0}
                      </td>
                      <td className="px-2 py-1.5 whitespace-nowrap text-xs font-mono text-gray-500">
                        {formatRelativeTime(game.start_time)}
                      </td>
                      <td className="px-2 py-1.5 whitespace-nowrap text-xs font-mono">
                        <Link href={`/match/${game.game_id}`} className="text-blue-600 hover:underline">
                          view
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Footer */}
        <div className="px-3 py-2 border-t border-gray-100 text-[10px] font-mono text-gray-400 text-right">
          {games.length} matches shown
        </div>
      </div>
    </div>
  );
}
