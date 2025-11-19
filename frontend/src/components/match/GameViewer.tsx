"use client"

import { useState, useEffect } from "react"
import { Copy } from "lucide-react"
import { Button } from "@/components/ui/button"
import GameCanvas from "./GameCanvas"
import PlayerThoughts from "./PlayerThoughts"
import GameControls from "./GameControls"
import VideoDownloadButton from "./VideoDownloadButton"

// Define color configuration types
interface PlayerColorScheme {
  main: string;       // Main color for the snake
  border: string;     // Border color for the thoughts panel
  shadow: string;     // Shadow color for the thoughts panel
  title_background: string;      // Title text color
}

interface ColorConfig {
  player1: PlayerColorScheme;
  player2: PlayerColorScheme;
}

// Define the game data structure types
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

interface GameViewerProps {
  gameData: GameData;
  modelIds: string[];
  modelNames: string[];
  colorConfig?: ColorConfig; // Optional custom color config
}

// Default color configuration
const defaultColorConfig: ColorConfig = {
  player1: {
    main: "#4F7022",
    border: "border-blue-500/20",
    shadow: "shadow-[0_0_15px_rgba(59,130,246,0.1)]",
    title_background: "bg-[#4F7022]"
  },
  player2: {
    main: "#036C8E",
    border: "border-purple-500/20",
    shadow: "shadow-[0_0_15px_rgba(147,51,234,0.1)]",
    title_background: "bg-[#036C8E]"
  }
};

export default function GameViewer({ 
  gameData, 
  modelIds, 
  modelNames,
  colorConfig = defaultColorConfig 
}: GameViewerProps) {
  const [currentRound, setCurrentRound] = useState(0);
  const [isPlaying, setIsPlaying] = useState(true);
  const playbackSpeed = 1;
  
  const totalRounds = gameData.rounds.length;
  const currentRoundData = gameData.rounds[currentRound];
  
  // Extract thoughts for current round
  const getThoughtsForModel = (modelId: string) => {
    if (currentRoundData && currentRoundData.move_history) {
      // If move_history is an array, get the last entry
      if (Array.isArray(currentRoundData.move_history) && currentRoundData.move_history.length > 0) {
        // Get the last move in the array
        const lastMove = currentRoundData.move_history[currentRoundData.move_history.length - 1];
        
        if (lastMove && lastMove[modelId] && lastMove[modelId].rationale) {
          const thoughts = lastMove[modelId].rationale.split('\n').filter(Boolean);
          return thoughts;
        }
      }
    }
    
    return ["No thoughts available for this round"];
  };

  // Auto-play functionality
  useEffect(() => {
    if (!isPlaying) return;
    
    const interval = setInterval(() => {
      setCurrentRound(prev => {
        if (prev >= totalRounds - 1) {
          setIsPlaying(false);
          return prev;
        }
        return prev + 1;
      });
    }, 500 / playbackSpeed);
    
    return () => clearInterval(interval);
  }, [isPlaying, totalRounds, playbackSpeed]);

  // Handle controls
  const handlePlay = () => setIsPlaying(!isPlaying);
  const handleNext = () => setCurrentRound(prev => Math.min(prev + 1, totalRounds - 1));
  const handlePrev = () => setCurrentRound(prev => Math.max(prev - 1, 0));
  const handleStart = () => setCurrentRound(0);
  const handleEnd = () => setCurrentRound(totalRounds - 1);
  
  const copyGameId = () => {
    navigator.clipboard.writeText(`${process.env.NEXT_PUBLIC_FRONTEND_URL}/match/${gameData.metadata.game_id}`);
  };

  return (
    <>
      <div className="grid grid-cols-[1fr_min-content_1fr] gap-4">
        {/* Left AI Thoughts */}
        <PlayerThoughts 
          modelName={modelNames[0]} 
          thoughts={getThoughtsForModel(modelIds[0])}
          score={currentRoundData.scores[modelIds[0]] || 0}
          isAlive={currentRoundData.alive[modelIds[0]] || false}
          color="player1"
          colorScheme={colorConfig.player1}
        />

        {/* Game Canvas */}
        <GameCanvas 
          snakePositions={currentRoundData.snake_positions}
          apples={currentRoundData.apples}
          width={currentRoundData.width}
          height={currentRoundData.height}
          modelIds={modelIds}
          colorConfig={{
            [modelIds[0]]: colorConfig.player1.main,
            [modelIds[1]]: colorConfig.player2.main
          }}
        />

        {/* Right AI Thoughts */}
        <PlayerThoughts 
          modelName={modelNames[1]} 
          thoughts={getThoughtsForModel(modelIds[1])}
          score={currentRoundData.scores[modelIds[1]] || 0}
          isAlive={currentRoundData.alive[modelIds[1]] || false}
          color="player2"
          colorScheme={colorConfig.player2}
        />
      </div>

      {/* Game controls */}
      <GameControls 
        currentRound={currentRound}
        totalRounds={totalRounds}
        isPlaying={isPlaying}
        onPlay={handlePlay}
        onNext={handleNext}
        onPrev={handlePrev}
        onStart={handleStart}
        onEnd={handleEnd}
      />

      {/* Game ID + download */}
      <div className="mt-6 flex flex-col items-center gap-3">
        <Button
          variant="outline"
          size="sm"
          className="text-sm text-gray-500 flex items-center gap-2 font-mono"
          onClick={copyGameId}
        >
          <span>Match ID: {gameData.metadata.game_id}</span>
          <Copy className="h-4 w-4" />
        </Button>
        <VideoDownloadButton matchId={gameData.metadata.game_id} />
      </div>
    </>
  )
} 
