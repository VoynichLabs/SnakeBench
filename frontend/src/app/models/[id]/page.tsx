import Link from 'next/link';

interface Game {
  game_id: string;
  my_score: number;
  opponent_score: number;
  opponent_model: string;
  start_time: string;
  opponent_elo: number;
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
  elo: number;
  total_cost?: number;
  games: Game[];
}

export default async function ModelDetailsPage({ params }: { params: Promise<{ id: string }> }) {
  // Await the params object
  const { id: encodedModelId } = await params;

  // Decode the URL-encoded model ID
  const modelId = decodeURIComponent(encodedModelId);

  // Fetch the full stats (encode it again for the URL)
  const response = await fetch(`${process.env.FLASK_URL}/api/stats?model=${encodeURIComponent(modelId)}`, { next: { revalidate: 300 } });
  const stats = await response.json();

  // Use the decoded modelId to look up in the response
  const modelStats: ModelStats = stats['aggregatedData'][modelId];

  if (!modelStats) {
    return (
      <div className="max-w-7xl mx-auto py-12 px-4 sm:px-6 lg:px-8">
        <div className="text-center">
          <h1 className="text-3xl font-extrabold text-gray-900 sm:text-4xl">
            Model Not Found
          </h1>
          <p className="mt-3 max-w-2xl mx-auto text-xl text-gray-500 sm:mt-4">
            Model &quot;{modelId}&quot; could not be found in our database.
          </p>
          <div className="mt-5">
            <Link href="/" className="text-indigo-600 hover:text-indigo-500">
              Return to home page
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const games = [...(modelStats.games || [])].sort((a, b) => new Date(b.start_time).getTime() - new Date(a.start_time).getTime());
  
  // Calculate win rate percentage (excludes ties from denominator)
  const decidedGames = modelStats.wins + modelStats.losses;
  const totalGames = modelStats.wins + modelStats.losses + modelStats.ties;
  const winRate = decidedGames > 0 ? ((modelStats.wins / decidedGames) * 100).toFixed(1) : "0.0";

  return (
    <div className="bg-white">
      {/* Model Header Section */}
      <div className="bg-gray-50 py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center">
            <h1 className="text-3xl font-extrabold text-gray-900 sm:text-4xl">
              {modelId}
            </h1>
            <p className="mt-3 max-w-2xl mx-auto text-xl text-gray-500 sm:mt-4">
              Performance statistics and match history
            </p>
          </div>
        </div>
      </div>

      {/* Model Stats Section */}
      <div className="max-w-7xl mx-auto py-12 px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-5">
          <div className="bg-white overflow-hidden shadow rounded-lg">
            <div className="px-4 py-5 sm:p-6">
              <dt className="text-sm font-medium text-gray-500 truncate">
                Total Matches
              </dt>
              <dd className="mt-1 text-3xl font-semibold text-gray-900">
                {totalGames}
              </dd>
            </div>
          </div>

          <div className="bg-white overflow-hidden shadow rounded-lg">
            <div className="px-4 py-5 sm:p-6">
              <dt className="text-sm font-medium text-gray-500 truncate">
                Win Rate
              </dt>
              <dd className="mt-1 text-3xl font-semibold text-gray-900">
                {winRate}%
              </dd>
            </div>
          </div>

          <div className="bg-white overflow-hidden shadow rounded-lg">
            <div className="px-4 py-5 sm:p-6">
              <dt className="text-sm font-medium text-gray-500 truncate">
                ELO Rating
              </dt>
              <dd className="mt-1 text-3xl font-semibold text-gray-900">
                {Math.round(modelStats.elo).toLocaleString()}
              </dd>
            </div>
          </div>

          <div className="bg-white overflow-hidden shadow rounded-lg">
            <div className="px-4 py-5 sm:p-6">
              <dt className="text-sm font-medium text-gray-500 truncate">
                Apples Eaten
              </dt>
              <dd className="mt-1 text-3xl font-semibold text-gray-900">
                {modelStats.apples_eaten}
              </dd>
            </div>
          </div>

          <div className="bg-white overflow-hidden shadow rounded-lg">
            <div className="px-4 py-5 sm:p-6">
              <dt className="text-sm font-medium text-gray-500 truncate">
                Total Cost
              </dt>
              <dd className="mt-1 text-3xl font-semibold text-gray-900">
                ${(modelStats.total_cost || 0).toFixed(4)}
              </dd>
            </div>
          </div>
        </div>
      </div>

      {/* Match History Section */}
      <div className="max-w-7xl mx-auto pb-12 px-4 sm:px-6 lg:px-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-6">Match History</h2>
        <div className="flex flex-col">
          <div className="-my-2 overflow-x-auto sm:-mx-6 lg:-mx-8">
            <div className="py-2 align-middle inline-block min-w-full sm:px-6 lg:px-8">
              <div className="shadow overflow-hidden border-b border-gray-200 sm:rounded-lg">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Opponent
                      </th>
                      <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Start Time
                      </th>
                      <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Duration
                      </th>
                      <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Outcome
                      </th>
                      <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Loss Reason
                      </th>
                      <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Score
                      </th>
                      <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Cost
                      </th>
                      <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {games.map((game, index) => {
                      // For a lost game, show the loss reason (if available)
                      const lossReason = game.result === "lost" && game.death_info ? game.death_info.reason : "";
                      
                      // Format the date
                      const formattedDate = new Date(game.start_time).toLocaleString('en-US', {
                        year: 'numeric',
                        month: '2-digit', 
                        day: '2-digit',
                        hour: 'numeric',
                        minute: '2-digit',
                        hour12: true
                      }).replace(',','');
                      
                      // Calculate duration
                      const start = new Date(game.start_time);
                      const end = new Date(game.end_time);
                      const diffMs = end.getTime() - start.getTime();
                      const minutes = Math.floor(diffMs / 60000);
                      const seconds = Math.floor((diffMs % 60000) / 1000);
                      const duration = `${minutes}min ${seconds}sec`;
                      
                      // Determine outcome styling
                      let outcomeClass = "";
                      if (game.result === "won") {
                        outcomeClass = "bg-green-100 text-green-800";
                      } else if (game.result === "lost") {
                        outcomeClass = "bg-red-100 text-red-800";
                      } else {
                        outcomeClass = "bg-gray-100 text-gray-800";
                      }
                      
                      return (
                        <tr key={game.game_id || index}>
                          <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                            <Link href={`/models/${game.opponent_model}`} className="text-indigo-600 hover:text-indigo-900">
                              {game.opponent_model}
                            </Link>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                            {formattedDate}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                            {duration}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${outcomeClass}`}>
                              {game.result.charAt(0).toUpperCase() + game.result.slice(1)}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                            {lossReason}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                            {game.my_score} - {game.opponent_score}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                            ${(game.cost || 0).toFixed(4)}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                            <Link href={`/match/${game.game_id}`} className="text-indigo-600 hover:text-indigo-900">
                              View Match
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
      </div>
      
      <div className="max-w-7xl mx-auto pb-12 px-4 sm:px-6 lg:px-8">
        <p className="text-center text-sm text-gray-500">
          Last updated: {new Date().toLocaleString()}
        </p>
      </div>
    </div>
  );
}

