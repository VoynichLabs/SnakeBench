"use client"

import { Play, SkipBack, SkipForward, ChevronsLeft, ChevronsRight, Pause } from "lucide-react"

interface GameControlsProps {
  currentRound: number;
  totalRounds: number;
  isPlaying: boolean;
  onPlay: () => void;
  onNext: () => void;
  onPrev: () => void;
  onStart: () => void;
  onEnd: () => void;
}

export default function GameControls({
  currentRound,
  totalRounds,
  isPlaying,
  onPlay,
  onNext,
  onPrev,
  onStart,
  onEnd
}: GameControlsProps) {
  const denominator = Math.max(totalRounds - 1, 1);
  const progressPercentage = totalRounds ? (currentRound / denominator) * 100 : 0;

  return (
    <div className="flex flex-col items-center gap-3">
      {/* Progress bar */}
      <div className="w-full max-w-md">
        <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
          <div
            className="h-full bg-blue-500 rounded-full transition-all duration-150"
            style={{ width: `${progressPercentage}%` }}
          />
        </div>
      </div>

      {/* Control buttons */}
      <div className="flex items-center gap-1">
        <button
          onClick={onStart}
          className="p-2 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-700 transition-colors"
        >
          <ChevronsLeft className="h-4 w-4" />
          <span className="sr-only">Start</span>
        </button>
        <button
          onClick={onPrev}
          className="p-2 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-700 transition-colors"
        >
          <SkipBack className="h-4 w-4" />
          <span className="sr-only">Previous</span>
        </button>
        <button
          onClick={onPlay}
          className="p-2.5 rounded-full bg-gray-900 hover:bg-gray-800 text-white transition-colors mx-1"
        >
          {isPlaying ? (
            <Pause className="h-5 w-5" />
          ) : (
            <Play className="h-5 w-5 ml-0.5" />
          )}
          <span className="sr-only">{isPlaying ? 'Pause' : 'Play'}</span>
        </button>
        <button
          onClick={onNext}
          className="p-2 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-700 transition-colors"
        >
          <SkipForward className="h-4 w-4" />
          <span className="sr-only">Next</span>
        </button>
        <button
          onClick={onEnd}
          className="p-2 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-700 transition-colors"
        >
          <ChevronsRight className="h-4 w-4" />
          <span className="sr-only">End</span>
        </button>
      </div>

      {/* Move counter */}
      <p className="font-mono text-[10px] text-gray-500">
        Round {currentRound + 1} / {totalRounds}
      </p>
    </div>
  );
} 
