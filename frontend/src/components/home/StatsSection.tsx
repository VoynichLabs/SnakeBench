// Import the type from LeaderboardSection or define it here
type StatsData = {
  totalGames: number;
  aggregatedData: {
    [key: string]: {
      wins: number;
      losses: number;
      ties: number;
      apples_eaten: number;
      rating?: number;
      elo?: number;
      first_game_time: string;
      last_game_time: string;
      top_score: number;
      total_cost: number;
    };
  };
};

async function getStats() {
  // Fetch the stats from the backend
  const response = await fetch(`${process.env.FLASK_URL}/api/stats?simple=true`, {
    cache: 'no-store' // Ensures fresh data on each request
  });
  
  if (!response.ok) {
    throw new Error('Failed to fetch stats');
  }
  
  const data = await response.json();
  return data;
}

export default async function StatsSection() {
  const stats = await getStats();
  
  // Check if stats has the expected structure
  const statsData = stats as StatsData;
  
  // Use totalGames from the API if available, otherwise calculate it
  const totalMatches = statsData.totalGames || Object.values(statsData.aggregatedData || {}).reduce((sum: number, model) => {
    const wins = Number(model.wins) || 0;
    const losses = Number(model.losses) || 0;
    const ties = Number(model.ties) || 0;
    return sum + wins + losses + ties;
  }, 0);
  
  // Count active models (models with at least one game)
  const activeModels = Object.keys(statsData.aggregatedData || {}).length;

  // Calculate maximum apples that were gained per game
  const maxApplesPerGame = totalMatches > 0 ? Math.max(...Object.values(statsData.aggregatedData || {}).map(model => Number(model.top_score || 0))) : 0;

  // Calculate total cost across all models
  const totalCost = Object.values(statsData.aggregatedData || {}).reduce((sum: number, model) => {
    return sum + (Number(model.total_cost) || 0);
  }, 0);

  return (
    <>

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4 mb-12">
        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <dt className="text-sm font-mono text-gray-500 truncate">Total Snake Matches</dt>
            <dd className="mt-1 text-3xl font-press-start text-gray-900">{totalMatches.toLocaleString()}</dd>
          </div>
        </div>
        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <dt className="text-sm font-mono text-gray-500 truncate">Models Competing</dt>
            <dd className="mt-1 text-3xl font-press-start text-gray-900">{activeModels}</dd>
          </div>
        </div>
        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <dt className="text-sm font-mono text-gray-500 truncate">Top Apples Eaten</dt>
            <dd className="mt-1 text-3xl font-press-start text-gray-900">{maxApplesPerGame}</dd>
          </div>
        </div>
        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <dt className="text-sm font-mono text-gray-500 truncate">Total Testing Cost</dt>
            <dd className="mt-1 text-3xl font-press-start text-gray-900">${totalCost.toFixed(2)}</dd>
          </div>
        </div>
      </div>
    </>
  );
} 
