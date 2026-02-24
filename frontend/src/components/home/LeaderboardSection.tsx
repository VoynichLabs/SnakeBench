import { createEloLikeScaler } from "@/lib/ratingScale";
import Link from "next/link";

type LeaderboardItem = {
  rank: number;
  model: string;
  wins: number;
  losses: number;
  winRate: number;
  rating: number;
  scaledRating: number;
  trueskillMu: number;
  trueskillSigma: number;
  trueskillExposed: number;
  top_score: number;
  total_cost: number;
  apples_eaten: number;
  ties: number;
};

type StatsData = {
  totalGames: number;
  aggregatedData: {
    [key: string]: {
      wins: number;
      losses: number;
      ties: number;
      apples_eaten: number;
      rating: number;
      trueskill_mu?: number;
      trueskill_sigma?: number;
      trueskill_exposed?: number;
      first_game_time: string;
      last_game_time: string;
      top_score: number;
      total_cost: number;
    };
  };
};

type CombinedData = {
  leaderboard: LeaderboardItem[];
  stats: {
    totalGames: number;
    modelCount: number;
    topScore: number;
    totalCost: number;
  };
};

// Function to fetch and transform leaderboard data
async function getCombinedData(): Promise<CombinedData> {
  try {
    const url = `${process.env.NEXT_PUBLIC_FLASK_URL}/api/stats?simple=true`;

    const response = await fetch(url);

    if (!response.ok) {
      throw new Error('Failed to fetch leaderboard data');
    }

    const data: StatsData = await response.json();

    const aggregatedEntries = Object.entries(data.aggregatedData || {});
    const ratingScaler = createEloLikeScaler(
      aggregatedEntries.map(([, stats]) => stats.trueskill_exposed ?? stats.rating ?? 0)
    );

    // Transform the API data into our leaderboard format
    const leaderboard = aggregatedEntries
      .map(([model, stats]) => ({
        model,
        wins: stats.wins,
        losses: stats.losses,
        ties: stats.ties,
        top_score: stats.top_score,
        total_cost: stats.total_cost,
        apples_eaten: stats.apples_eaten || 0,
        winRate: stats.wins + stats.losses > 0
          ? Math.round((stats.wins / (stats.wins + stats.losses)) * 100)
          : 0,
        rating: stats.trueskill_exposed ?? stats.rating ?? 0,
        trueskillMu: stats.trueskill_mu ?? 0,
        trueskillSigma: stats.trueskill_sigma ?? 0,
        trueskillExposed: stats.trueskill_exposed ?? stats.rating ?? 0,
        scaledRating: ratingScaler.scale(stats.trueskill_exposed ?? stats.rating ?? 0),
      }))
      .filter(item => item.wins + item.losses + item.ties >= 1)
      .sort((a, b) => b.rating - a.rating)
      .map((item, index) => ({
        ...item,
        rank: index + 1,
      }))
      .slice(0, 1000);

    // Calculate stats
    const totalGames = data.totalGames || 0;
    const modelCount = aggregatedEntries.length;
    const topScore = Math.max(...aggregatedEntries.map(([, s]) => s.top_score || 0), 0);
    const totalCost = aggregatedEntries.reduce((sum, [, s]) => sum + (s.total_cost || 0), 0);

    return {
      leaderboard,
      stats: { totalGames, modelCount, topScore, totalCost }
    };
  } catch (err) {
    console.error('[LeaderboardSection] Error fetching data:', err);
    throw err;
  }
}

export default async function LeaderboardSection() {
  const { leaderboard, stats } = await getCombinedData();

  if (leaderboard.length === 0) {
    return (
      <div className="bg-white border border-gray-200 p-4">
        <p className="text-sm font-mono text-red-500">Failed to load leaderboard data</p>
      </div>
    );
  }

  return (
    <div className="bg-white border border-gray-200">
      {/* Compact header row with description, live indicator, and stats */}
      <div className="px-3 py-2 border-b border-gray-200 flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
        <div className="flex items-center gap-4 text-xs font-mono text-gray-500">
          <span>Two LLM snakes enter</span>
          <span className="text-gray-300">→</span>
          <span>One survives longest</span>
          <span className="text-gray-300">→</span>
          <span>Repeat</span>
          <div className="flex items-center gap-1 ml-1">
            <div className="relative">
              <div className="h-1.5 w-1.5 rounded-full bg-red-500 absolute animate-ping"></div>
              <div className="h-1.5 w-1.5 rounded-full bg-red-500 relative"></div>
            </div>
            <span className="text-[10px] font-mono uppercase tracking-wider text-red-500">LIVE</span>
          </div>
        </div>

        {/* Inline stats */}
        <div className="flex items-center gap-4 text-xs font-mono text-gray-500">
          <span><span className="text-gray-900 font-medium">{stats.totalGames.toLocaleString()}</span> games</span>
          <span><span className="text-gray-900 font-medium">{stats.modelCount}</span> models</span>
          <span>top: <span className="text-gray-900 font-medium">{stats.topScore}</span></span>
          <span>cost: <span className="text-gray-900 font-medium">${stats.totalCost.toFixed(2)}</span></span>
          <Link href="/live-games" className="text-blue-600 hover:text-blue-800 hover:underline">
            watch live
          </Link>
        </div>
      </div>

      {/* Compact table */}
      <div className="overflow-x-auto">
        <table className="min-w-full">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="px-2 py-1.5 text-left text-[10px] font-mono text-gray-500 uppercase tracking-wider">#</th>
              <th className="px-2 py-1.5 text-left text-[10px] font-mono text-gray-500 uppercase tracking-wider">Model</th>
              <th className="px-2 py-1.5 text-left text-[10px] font-mono text-gray-500 uppercase tracking-wider">
                <span className="group relative cursor-help">
                  Rating
                  <span className="pointer-events-none absolute left-0 top-full mt-1 w-48 rounded bg-gray-900 text-white text-[10px] p-1.5 opacity-0 group-hover:opacity-100 transition-opacity z-10">
                    TrueSkill exposed rating
                  </span>
                </span>
              </th>
              <th className="px-2 py-1.5 text-left text-[10px] font-mono text-gray-500 uppercase tracking-wider">
                <span className="group relative cursor-help">
                  ±σ
                  <span className="pointer-events-none absolute left-0 top-full mt-1 w-40 rounded bg-gray-900 text-white text-[10px] p-1.5 opacity-0 group-hover:opacity-100 transition-opacity z-10">
                    Uncertainty (&lt;3 = confident)
                  </span>
                </span>
              </th>
              <th className="px-2 py-1.5 text-left text-[10px] font-mono text-gray-500 uppercase tracking-wider">W/L</th>
              <th className="px-2 py-1.5 text-left text-[10px] font-mono text-gray-500 uppercase tracking-wider">Win%</th>
              <th className="px-2 py-1.5 text-left text-[10px] font-mono text-gray-500 uppercase tracking-wider">Apples</th>
              <th className="px-2 py-1.5 text-left text-[10px] font-mono text-gray-500 uppercase tracking-wider">Best</th>
              <th className="px-2 py-1.5 text-left text-[10px] font-mono text-gray-500 uppercase tracking-wider">Cost</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {leaderboard.map((item, i) => (
              <tr
                key={item.model}
                className={`hover:bg-blue-50 transition-colors ${i < 3 ? 'bg-amber-50/40' : ''}`}
              >
                <td className="px-2 py-1 whitespace-nowrap text-xs font-mono text-gray-400">
                  {item.rank}
                </td>
                <td className="px-2 py-1 whitespace-normal max-w-[180px]">
                  <Link
                    href={`/models/${item.model}`}
                    className="font-mono text-xs text-gray-900 hover:text-blue-600 hover:underline break-words"
                  >
                    {item.model}
                  </Link>
                </td>
                <td className="px-2 py-1 whitespace-nowrap text-xs font-mono text-gray-900 font-medium" title={`μ=${item.trueskillMu.toFixed(3)}`}>
                  {item.trueskillExposed.toFixed(1)}
                </td>
                <td className="px-2 py-1 whitespace-nowrap text-xs font-mono text-gray-400">
                  {item.trueskillSigma.toFixed(1)}
                </td>
                <td className="px-2 py-1 whitespace-nowrap text-xs font-mono text-gray-600">
                  {item.wins}/{item.losses}
                </td>
                <td className="px-2 py-1 whitespace-nowrap text-xs font-mono text-gray-600">
                  {item.winRate}%
                </td>
                <td className="px-2 py-1 whitespace-nowrap text-xs font-mono text-gray-600">
                  {item.apples_eaten}
                </td>
                <td className="px-2 py-1 whitespace-nowrap text-xs font-mono text-gray-600">
                  {item.top_score}
                </td>
                <td className="px-2 py-1 whitespace-nowrap text-xs font-mono text-gray-400">
                  ${(item.total_cost || 0).toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
} 
