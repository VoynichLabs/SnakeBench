import { createEloLikeScaler } from "@/lib/ratingScale";

type LeaderboardItem = {
  rank: number;
  model: string;
  wins: number;
  losses: number;
  winRate: number;
  rating: number;
  scaledRating: number;
  top_score: number;
  total_cost: number;
  apples_eaten: number;
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
      first_game_time: string;
      last_game_time: string;
      top_score: number;
      total_cost: number;
    };
  };
};

// Function to fetch and transform leaderboard data
async function getLeaderboardData(): Promise<LeaderboardItem[]> {
  try {
    const url = `${process.env.FLASK_URL}/api/stats?simple=true`;
    console.log('[LeaderboardSection] Fetching from:', url);

    const response = await fetch(url);
    console.log('[LeaderboardSection] Response status:', response.status);

    if (!response.ok) {
      const errorText = await response.text();
      console.error('[LeaderboardSection] Error response:', errorText);
      throw new Error('Failed to fetch leaderboard data');
    }

    const data: StatsData = await response.json();
    console.log('[LeaderboardSection] Received data:', {
      totalGames: data.totalGames,
      modelCount: Object.keys(data.aggregatedData || {}).length
    });

    const aggregatedEntries = Object.entries(data.aggregatedData || {});
    const ratingScaler = createEloLikeScaler(
      aggregatedEntries.map(([, stats]) => stats.rating)
    );
    
    // Transform the API data into our leaderboard format
    const transformedData = aggregatedEntries
      .map(([model, stats]) => ({
        model,
        wins: stats.wins,
        losses: stats.losses,
        ties: stats.ties,
        top_score: stats.top_score,
        total_cost: stats.total_cost,
        apples_eaten: stats.apples_eaten || 0,
        winRate: stats.wins + stats.losses > 0
          ? Number(((stats.wins / (stats.wins + stats.losses)) * 100).toFixed(1))
          : 0,
        rating: stats.rating ?? 0,
        scaledRating: ratingScaler.scale(stats.rating),
      }))
      .filter(item => item.wins + item.losses + item.ties >= 1) // Show all models
      .sort((a, b) => b.rating - a.rating) // Sort by rating
      .map((item, index) => ({
        ...item,
        rank: index + 1,
      }))
      .slice(0, 1000); // Take top 10

    console.log('[LeaderboardSection] Transformed data:', {
      itemCount: transformedData.length,
      firstItem: transformedData[0]
    });
    return transformedData;
  } catch (err) {
    console.error('[LeaderboardSection] Error fetching leaderboard data:', err);
    throw err; // Re-throw to see error in UI
  }
}

export default async function LeaderboardSection() {
  const leaderboardData = await getLeaderboardData();
  
  if (leaderboardData.length === 0) {
    return (
      <div className="bg-white shadow rounded-lg overflow-hidden p-6">
        <h2 className="text-lg font-press-start text-gray-900">Global Leaderboard</h2>
        <p className="mt-1 text-sm font-mono text-red-500">Failed to load leaderboard data</p>
      </div>
    );
  }

  return (
    <div className="bg-white shadow rounded-lg overflow-hidden">
      <div className="px-4 py-5 border-b border-gray-200 sm:px-6">
        <div className="flex items-center">
          <h2 className="text-lg font-press-start text-gray-900">Global Leaderboard</h2>
          <div className="flex items-center ml-3">
            <div className="relative mr-1">
              <div className="h-2 w-2 rounded-full bg-red-500 absolute animate-ping"></div>
              <div className="h-2 w-2 rounded-full bg-red-500 relative"></div>
            </div>
            <span className="text-xs font-mono uppercase tracking-wider text-red-500">LIVE</span>
          </div>
        </div>
        <p className="mt-1 text-sm font-mono text-gray-500">Updated in real-time based on match results</p>
      </div>
      <div className="px-4 sm:px-6 py-4">
        <div className="flex flex-col">
          <div className="-my-2 overflow-x-auto sm:-mx-6 lg:-mx-8">
            <div className="py-2 align-middle inline-block min-w-full sm:px-6 lg:px-8">
              <div className="overflow-hidden">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th
                        scope="col"
                        className="px-6 py-3 text-left text-xs font-mono text-gray-500 uppercase tracking-wider"
                      >
                        Rank
                      </th>
                      <th
                        scope="col"
                        className="px-6 py-3 text-left text-xs font-mono text-gray-500 uppercase tracking-wider"
                      >
                        Model
                      </th>
                      <th
                        scope="col"
                        className="px-6 py-3 text-left text-xs font-mono text-gray-500 uppercase tracking-wider"
                      >
                        W/L
                      </th>
                      <th
                        scope="col"
                        className="px-6 py-3 text-left text-xs font-mono text-gray-500 uppercase tracking-wider"
                      >
                        Apples
                      </th>
                      <th
                        scope="col"
                        className="px-6 py-3 text-left text-xs font-mono text-gray-500 uppercase tracking-wider"
                      >
                        Top Score
                      </th>
                      <th
                        scope="col"
                        className="px-6 py-3 text-left text-xs font-mono text-gray-500 uppercase tracking-wider"
                      >
                        Win Rate
                      </th>
                      <th
                        scope="col"
                        className="px-6 py-3 text-left text-xs font-mono text-gray-500 uppercase tracking-wider"
                      >
                        <span title="This is TrueSkill rating, but it's scaled to whatever to more closely match ELO scale, which is common across the industry.">
                          Rating
                        </span>
                      </th>
                      <th
                        scope="col"
                        className="px-6 py-3 text-left text-xs font-mono text-gray-500 uppercase tracking-wider"
                      >
                        Cost
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {leaderboardData.map((item) => (
                      <tr key={item.model} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-gray-900">
                          #{item.rank}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <a href={`/models/${item.model}`} className="font-mono text-sm text-blue-600 hover:text-blue-800 hover:underline">
                            {item.model}
                          </a>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="font-mono text-sm text-gray-900">
                            {item.wins}/{item.losses}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="font-mono text-sm text-gray-900">{item.apples_eaten}</div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="font-mono text-sm text-gray-900">{item.top_score}</div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="font-mono text-sm text-gray-900">{item.winRate}%</div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div
                            className="font-mono text-sm text-gray-900"
                            title={`TrueSkill: ${item.rating.toFixed(2)} (display scaled to ELO-like range)`}
                          >
                            {item.scaledRating.toLocaleString()}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="font-mono text-sm text-gray-900">
                            ${(item.total_cost || 0).toFixed(4)}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
} 
