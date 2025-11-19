import { notFound } from 'next/navigation'
import MatchInfo from '@/components/match/MatchInfo'
import GameViewer from '@/components/match/GameViewer'

// Use the same type definitions as in GameViewer.tsx
type Position = [number, number];

interface MoveHistory {
  [modelId: string]: {
    move: string;
    rationale: string;
  };
}

interface RoundData {
  round_number: number;
  move_history?: MoveHistory[];
  snake_positions: {
    [modelId: string]: Position[];
  };
  alive: {
    [modelId: string]: boolean;
  };
  scores: {
    [modelId: string]: number;
  };
  apples: Position[];
  width: number;
  height: number;
}

interface GameMetadata {
  game_id: string;
  start_time: string;
  end_time: string;
  models: Record<string, string>;
  game_result: Record<string, string>;
  final_scores: Record<string, number>;
  death_info: Record<string, { reason: string, round?: number }>;
  max_rounds: number;
  actual_rounds: number;
}

interface GameData {
  rounds: RoundData[];
  metadata: GameMetadata;
}

interface PageProps {
  params: Promise<{
    id: string;
  }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}

export default async function MatchPage(props: PageProps) {
  const params = await props.params;
  const { id } = params;

  // Fetch replay directly from Supabase Storage
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const bucket = 'matches';
  const replayUrl = `${supabaseUrl}/storage/v1/object/public/${bucket}/${id}/replay.json`;

  const gamesResponse = await fetch(replayUrl, { next: { revalidate: 300 } }); // revalidate every 5 minutes

  // If not found or error
  if (!gamesResponse.ok) {
    notFound();
  }

  // Parse the JSON
  const gameData: GameData = await gamesResponse.json();

  // Format date for display
  const startTime = new Date(gameData.metadata.start_time);
  const formattedDate = startTime.toLocaleDateString('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  });
  const formattedTime = startTime.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });

  // Get model names for display
  const modelIds = Object.keys(gameData.metadata.models);
  const modelNames = modelIds.map(id => gameData.metadata.models[id]);

  return (
    <div className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
      <div className="px-4 py-6 sm:px-0">
        <MatchInfo
          modelNames={modelNames}
          date={formattedDate}
          time={formattedTime}
          matchId={id}
        />

        <GameViewer
          gameData={gameData}
          modelIds={modelIds}
          modelNames={modelNames}
        />
      </div>
    </div>
  )
}
