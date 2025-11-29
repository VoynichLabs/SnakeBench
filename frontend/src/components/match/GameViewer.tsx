"use client"

import { useState, useEffect, useRef } from "react"
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

// Replay types (normalized for both new + legacy schemas)
export type Position = [number, number]

export type MoveEntry = {
  move: string
  rationale?: string
  input_tokens?: number
  output_tokens?: number
  cost?: number
}

export type FrameState = {
  snakes: Record<string, Position[]>
  apples: Position[]
  alive: Record<string, boolean>
  scores: Record<string, number>
}

export type NormalizedFrame = {
  round: number
  state: FrameState
  moves?: Record<string, MoveEntry>
  events?: unknown[]
}

export type BoardInfo = {
  width: number
  height: number
  num_apples?: number
}

interface GameViewerProps {
  frames: NormalizedFrame[];
  board: BoardInfo;
  modelIds: string[];
  modelNames: string[];
  gameId: string;
  colorConfig?: ColorConfig; // Optional custom color config
  liveMode?: boolean;
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
  frames,
  board,
  modelIds, 
  modelNames,
  gameId,
  colorConfig = defaultColorConfig,
  liveMode = false
}: GameViewerProps) {
  const [currentRound, setCurrentRound] = useState(0);
  const [isPlaying, setIsPlaying] = useState(true);
  const [wasAutoStopped, setWasAutoStopped] = useState(false);
  const playbackSpeed = 1;
  const prevTotalRoundsRef = useRef(frames.length);
  
  const totalRounds = frames.length;
  const currentRoundData = frames[currentRound] || frames[frames.length - 1];
  
  // Extract thoughts for current round
  const getThoughtsForModel = (modelId: string) => {
    if (liveMode && (!currentRoundData?.moves || !currentRoundData.moves[modelId]?.rationale)) {
      return ["Waiting for live move and rationale..."];
    }

    if (currentRoundData && currentRoundData.moves) {
      const move = currentRoundData.moves[modelId];
      if (move?.rationale) {
        const thoughts = move.rationale.split('\n').filter(Boolean);
        return thoughts;
      }
    }
    
    return ["No thoughts available for this round"];
  };

  // Auto-play functionality
  useEffect(() => {
    if (!isPlaying) return;
    if (!totalRounds) return;
    
    const interval = setInterval(() => {
      setCurrentRound(prev => {
        if (prev >= totalRounds - 1) {
          setIsPlaying(false);
          setWasAutoStopped(true);
          return prev;
        }
        return prev + 1;
      });
    }, 500 / playbackSpeed);
    
    return () => clearInterval(interval);
  }, [isPlaying, totalRounds, playbackSpeed]);

  // Keep playback in sync when new frames stream in
  useEffect(() => {
    if (!liveMode) {
      prevTotalRoundsRef.current = totalRounds;
      return;
    }

    const gainedFrame = totalRounds > prevTotalRoundsRef.current;
    const wasAtEnd = currentRound >= prevTotalRoundsRef.current - 1;

    if (gainedFrame && wasAutoStopped && wasAtEnd) {
      setIsPlaying(true);
      setWasAutoStopped(false);
    }

    if (currentRound > Math.max(totalRounds - 1, 0)) {
      setCurrentRound(Math.max(totalRounds - 1, 0));
    }

    prevTotalRoundsRef.current = totalRounds;
  }, [totalRounds, currentRound, liveMode, wasAutoStopped]);

  // Handle controls
  const handlePlay = () => {
    setWasAutoStopped(false);
    setIsPlaying(prev => !prev);
  };
  const handleNext = () => setCurrentRound(prev => Math.min(prev + 1, totalRounds - 1));
  const handlePrev = () => setCurrentRound(prev => Math.max(prev - 1, 0));
  const handleStart = () => setCurrentRound(0);
  const handleEnd = () => setCurrentRound(totalRounds - 1);
  
  const copyGameId = () => {
    navigator.clipboard.writeText(`${process.env.NEXT_PUBLIC_FRONTEND_URL}/match/${gameId}`);
  };

  if (!currentRoundData) {
    return (
      <div className="mt-6 text-center text-sm text-gray-500">
        Replay data unavailable for this match.
      </div>
    )
  }

  const snakePositions = currentRoundData.state.snakes || {};
  const apples = currentRoundData.state.apples || [];
  const alive = currentRoundData.state.alive || {};
  const scores = currentRoundData.state.scores || {};
  const boardWidth = board.width || 10;
  const boardHeight = board.height || 10;

  return (
    <>
      <div className="grid grid-cols-[1fr_min-content_1fr] gap-4">
        {/* Left AI Thoughts */}
        <PlayerThoughts 
          modelName={modelNames[0]} 
          thoughts={getThoughtsForModel(modelIds[0])}
          score={scores[modelIds[0]] || 0}
          isAlive={alive[modelIds[0]] || false}
          color="player1"
          colorScheme={colorConfig.player1}
        />

        {/* Game Canvas */}
        <GameCanvas 
          snakePositions={snakePositions}
          apples={apples}
          width={boardWidth}
          height={boardHeight}
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
          score={scores[modelIds[1]] || 0}
          isAlive={alive[modelIds[1]] || false}
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
          <span>Match ID: {gameId}</span>
          <Copy className="h-4 w-4" />
        </Button>
        {!liveMode && <VideoDownloadButton matchId={gameId} />}
      </div>
    </>
  )
} 
