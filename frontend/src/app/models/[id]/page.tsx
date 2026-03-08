import Link from 'next/link';
import { createEloLikeScaler } from '@/lib/ratingScale';

interface Game {
  game_id: string;
  my_score: number;
  opponent_score: number;
  opponent_model: string;
  start_time: string;
  opponent_rating?: number;
  opponent_rank?: number;
  end_time: string;
  result: string;
  cost?: number;
  death_info?: {
    reason: string;
    round: number;
  };
}

interface ModelStats {
  wins: number;
  losses: number;
  ties: number;
  apples_eaten: number;
  rating?: number;
  trueskill_mu?: number;
  trueskill_sigma?: number;
  trueskill_exposed?: number;
  total_cost?: number;
  top_score?: number;
  games: Game[];
}

export default async function ModelDetailsPage({ params }: { params: Promise<{ id: string }> }) {
  // Await the params object
  const { id: encodedModelId } = await params;

  // Decode the URL-encoded model ID
  const modelId = decodeURIComponent(encodedModelId);

  // Fetch the full stats (encode it again for the URL)
  const response = await fetch(`${process.env.NEXT_PUBLIC_FLASK_URL}/api/stats?model=${encodeURIComponent(modelId)}`, { next: { revalidate: 300 } });
  const stats = await response.json();

  // Use the decoded modelId to look up in the response
  const modelStats: ModelStats = stats['aggregatedData'][modelId];

  if (!modelStats) {
    return (
      <div className="max-w-7xl mx-auto py-8 px-4">
        <div className="bg-white border border-gray-200 p-4">
          <h1 className="text-lg font-mono text-gray-900">Model Not Found</h1>
          <p className="mt-2 text-sm font-mono text-gray-500">
            Model &quot;{modelId}&quot; could not be found.
          </p>
          <Link href="/" className="mt-3 inline-block text-xs font-mono text-blue-600 hover:underline">
            ← Back to leaderboard
          </Link>
        </div>
      </div>
    );
  }

  const games = [...(modelStats.games || [])].sort((a, b) => new Date(b.start_time).getTime() - new Date(a.start_time).getTime());
  const ratingScaler = createEloLikeScaler([
    modelStats.rating,
    ...games.map((game) => game.opponent_rating)
  ]);

  // Calculate win rate percentage (excludes ties from denominator)
  const decidedGames = modelStats.wins + modelStats.losses;
  const totalGames = modelStats.wins + modelStats.losses + modelStats.ties;
  const winRate = decidedGames > 0 ? Math.round((modelStats.wins / decidedGames) * 100) : 0;
  const bestScore = modelStats.top_score ?? Math.max(...games.map(g => g.my_score), 0);
  const avgScore = games.length > 0 ? (games.reduce((sum, g) => sum + g.my_score, 0) / games.length).toFixed(1) : "0";

  return (
    <div className="max-w-7xl mx-auto py-4 px-4">
      <div className="bg-white border border-gray-200">
        {/* Compact header with model name and inline stats */}
        <div className="px-3 py-2 border-b border-gray-200">
          <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
            {/* Model name - prominent */}
            <div className="flex items-center gap-3">
              <Link href="/" className="text-xs font-mono text-gray-400 hover:text-blue-600">
                ←
              </Link>
              <h1 className="text-lg font-mono font-bold text-gray-900">
                {modelId}
              </h1>
            </div>

            {/* Inline stats bar */}
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs font-mono text-gray-500">
              <span>
                <span className="text-gray-900 font-medium">{totalGames}</span> matches
              </span>
              <span className="text-gray-300">|</span>
              <span>
                <span className="text-gray-900 font-medium">{modelStats.wins}</span>W / <span className="text-gray-900 font-medium">{modelStats.losses}</span>L / <span className="text-gray-900 font-medium">{modelStats.ties}</span>T
              </span>
              <span className="text-gray-300">|</span>
              <span>
                win: <span className="text-gray-900 font-medium">{winRate}%</span>
              </span>
              <span className="text-gray-300">|</span>
              <span className="group relative cursor-help">
                rating: <span className="text-gray-900 font-medium" title={`μ=${modelStats.trueskill_mu?.toFixed(2) ?? '—'}, σ=${modelStats.trueskill_sigma?.toFixed(2) ?? '—'}`}>
                  {modelStats.trueskill_exposed?.toFixed(1) ?? modelStats.rating?.toFixed(1) ?? '—'}
                </span>
                {modelStats.trueskill_sigma !== undefined && (
                  <span className="text-gray-400"> ±{modelStats.trueskill_sigma.toFixed(1)}</span>
                )}
              </span>
              <span className="text-gray-300">|</span>
              <span>
                apples: <span className="text-gray-900 font-medium">{modelStats.apples_eaten.toLocaleString()}</span>
              </span>
              <span className="text-gray-300">|</span>
              <span>
                best: <span className="text-gray-900 font-medium">{bestScore}</span>
              </span>
              <span className="text-gray-300">|</span>
              <span>
                avg: <span className="text-gray-900 font-medium">{avgScore}</span>
              </span>
              <span className="text-gray-300">|</span>
              <span>
                cost: <span className="text-gray-900 font-medium">${(modelStats.total_cost || 0).toFixed(4)}</span>
              </span>
            </div>
          </div>
        </div>

        {/* Match History Table - compact */}
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="pl-6 pr-2 py-1.5 text-left text-[10px] font-mono text-gray-500 uppercase tracking-wider">Opponent</th>
                <th className="px-2 py-1.5 text-left text-[10px] font-mono text-gray-500 uppercase tracking-wider">Time</th>
                <th className="px-2 py-1.5 text-left text-[10px] font-mono text-gray-500 uppercase tracking-wider">Duration</th>
                <th className="px-2 py-1.5 text-left text-[10px] font-mono text-gray-500 uppercase tracking-wider">Result</th>
                <th className="px-2 py-1.5 text-left text-[10px] font-mono text-gray-500 uppercase tracking-wider">Score</th>
                <th className="px-2 py-1.5 text-left text-[10px] font-mono text-gray-500 uppercase tracking-wider">Death</th>
                <th className="px-2 py-1.5 text-left text-[10px] font-mono text-gray-500 uppercase tracking-wider">Cost</th>
                <th className="px-2 py-1.5 text-left text-[10px] font-mono text-gray-500 uppercase tracking-wider"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {games.map((game, index) => {
                // For a lost game, show the loss reason (if available)
                const lossReason = game.result === "lost" && game.death_info ? game.death_info.reason : "";

                // Format the date compactly
                const date = new Date(game.start_time);
                const formattedDate = `${(date.getMonth() + 1).toString().padStart(2, '0')}/${date.getDate().toString().padStart(2, '0')} ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;

                // Calculate duration
                const start = new Date(game.start_time);
                const end = game.end_time ? new Date(game.end_time) : null;
                let duration: string;
                if (!end || isNaN(end.getTime()) || end.getTime() <= start.getTime()) {
                  duration = "...";
                } else {
                  const diffMs = end.getTime() - start.getTime();
                  const minutes = Math.floor(diffMs / 60000);
                  const seconds = Math.floor((diffMs % 60000) / 1000);
                  duration = `${minutes}:${seconds.toString().padStart(2, '0')}`;
                }

                // Determine outcome styling - more compact
                let resultDisplay: React.ReactNode;
                if (game.result === "won") {
                  resultDisplay = <span className="text-green-600 font-medium">W</span>;
                } else if (game.result === "lost") {
                  resultDisplay = <span className="text-red-600 font-medium">L</span>;
                } else {
                  resultDisplay = <span className="text-gray-500">T</span>;
                }

                // Row background based on result
                const rowBg = game.result === "won"
                  ? "bg-green-50/50"
                  : game.result === "lost"
                    ? "bg-red-50/50"
                    : "";

                return (
                  <tr key={game.game_id || index} className={`${rowBg} hover:bg-blue-50 transition-colors`}>
                    <td className="pl-6 pr-2 py-1 whitespace-nowrap">
                      <Link
                        href={`/models/${encodeURIComponent(game.opponent_model)}`}
                        className="text-xs font-mono text-gray-900 hover:text-blue-600 hover:underline"
                      >
                        {game.opponent_model}
                        {game.opponent_rank && <span className="text-gray-400 ml-1">#{game.opponent_rank}</span>}
                      </Link>
                    </td>
                    <td className="px-2 py-1 whitespace-nowrap text-xs font-mono text-gray-500">
                      {formattedDate}
                    </td>
                    <td className="px-2 py-1 whitespace-nowrap text-xs font-mono text-gray-500">
                      {duration}
                    </td>
                    <td className="px-2 py-1 whitespace-nowrap text-xs font-mono">
                      {resultDisplay}
                    </td>
                    <td className="px-2 py-1 whitespace-nowrap text-xs font-mono text-gray-600">
                      {game.my_score}-{game.opponent_score}
                    </td>
                    <td className="px-2 py-1 whitespace-nowrap text-xs font-mono text-gray-400 max-w-[100px] truncate" title={lossReason}>
                      {lossReason || "—"}
                    </td>
                    <td className="px-2 py-1 whitespace-nowrap text-xs font-mono text-gray-400">
                      ${(game.cost || 0).toFixed(4)}
                    </td>
                    <td className="px-2 py-1 whitespace-nowrap text-xs font-mono">
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

        {/* Footer */}
        <div className="px-3 py-2 border-t border-gray-100 text-[10px] font-mono text-gray-400 text-right">
          {games.length} matches shown
        </div>
      </div>
    </div>
  );
}
