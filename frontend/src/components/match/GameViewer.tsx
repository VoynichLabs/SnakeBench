"use client"

import { useState, useEffect, useRef } from "react"
import { Copy, ChevronDown } from "lucide-react"
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
  const renderAppleRow = (score: number) => {
    const tens = Math.floor(score / 10);
    const ones = score % 10;
    const maxIcons = 8;
    const icons: string[] = [];

    for (let i = 0; i < tens && icons.length < maxIcons; i++) icons.push("🍏");
    for (let i = 0; i < ones && icons.length < maxIcons; i++) icons.push("🍎");

    return (
      <div className="flex items-center gap-1 text-[11px] sm:text-xs font-mono text-gray-700">
        <span className="text-gray-500">{score}</span>
        <div className="flex flex-wrap gap-0.5 leading-none">
          {icons.map((icon, idx) => (
            <span key={idx} className="text-sm leading-none">
              {icon}
            </span>
          ))}
        </div>
      </div>
    );
  };

  const renderThoughtAccordion = (playerIndex: number, orderClass: string) => {
    const modelId = modelIds[playerIndex];
    const score = scores[modelId] || 0;
    const isAlive = alive[modelId] || false;
    const playerScheme = playerIndex === 0 ? colorConfig.player1 : colorConfig.player2;

    return (
      <details className={`group border border-gray-200 rounded-lg bg-white shadow-sm ${orderClass} min-w-0`}>
        <summary className="flex items-center justify-between gap-3 px-3 py-2 cursor-pointer list-none select-none">
          <div className="flex flex-col gap-1 min-w-0">
            {renderAppleRow(score)}
            <span
              className="font-press-start text-[8px] sm:text-[9px] leading-tight break-words px-2 py-1 rounded text-white bg-[var(--player-color)] sm:bg-transparent sm:text-gray-800 sm:px-0 sm:py-0 sm:rounded-none"
              style={{ ["--player-color" as string]: playerScheme.main }}
            >
              {modelNames[playerIndex]}
            </span>
          </div>
          <ChevronDown className="h-4 w-4 text-gray-400 transition-transform group-open:rotate-180" />
        </summary>
        <div className="px-3 pb-3">
          <PlayerThoughts 
            modelName={modelNames[playerIndex]} 
            thoughts={getThoughtsForModel(modelId)}
            score={score}
            isAlive={isAlive}
            color={playerIndex === 0 ? "player1" : "player2"}
            colorScheme={playerIndex === 0 ? colorConfig.player1 : colorConfig.player2}
          />
        </div>
      </details>
    );
  };

  return (
    <>
      {/* Mobile / tablet: compact accordions above the board */}
      <div className="space-y-4 lg:hidden">
        {/* Compact thoughts accordions */}
        <div className="grid grid-cols-2 gap-3">
          {renderThoughtAccordion(0, "order-1")}
          {renderThoughtAccordion(1, "order-2")}
        </div>

        {/* Game Canvas */}
        <div className="w-full max-w-3xl mx-auto">
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
        </div>
      </div>

      {/* Desktop: full-width side panels with centered board */}
      <div className="hidden lg:grid grid-cols-[1fr_minmax(360px,_1fr)_1fr] gap-6 items-start">
        <PlayerThoughts 
          modelName={modelNames[0]} 
          thoughts={getThoughtsForModel(modelIds[0])}
          score={scores[modelIds[0]] || 0}
          isAlive={alive[modelIds[0]] || false}
          color="player1"
          colorScheme={colorConfig.player1}
        />

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
      <div className="mt-6 flex flex-col items-center gap-3 w-full px-2 sm:px-0">
        <Button
          variant="outline"
          size="sm"
          className="w-full sm:w-auto max-w-xl text-xs sm:text-sm text-gray-500 flex items-center justify-center gap-2 font-mono whitespace-normal break-all leading-snug"
          onClick={copyGameId}
        >
          <span className="text-center">Match ID: {gameId}</span>
          <Copy className="h-4 w-4" />
        </Button>
        {!liveMode && <VideoDownloadButton matchId={gameId} />}
      </div>
    </>
  )
} 
