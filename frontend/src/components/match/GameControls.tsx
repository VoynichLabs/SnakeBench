"use client"

import { Play, SkipBack, SkipForward, ChevronsLeft, ChevronsRight, Pause } from "lucide-react"
import { Button } from "@/components/ui/button"

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
    <div className="mt-6 flex flex-col items-center gap-4">
      {/* Progress bar */}
      <div className="w-full max-w-md h-1 bg-gray-100 rounded-full overflow-hidden">
        <div 
          className="h-full bg-blue-500 rounded-full" 
          style={{ width: `${progressPercentage}%` }}
        />
      </div>

      {/* Control buttons */}
      <div className="flex items-center gap-2">
        <Button variant="outline" size="icon" className="h-8 w-8" onClick={onStart}>
          <ChevronsLeft className="h-4 w-4" />
          <span className="sr-only">Start</span>
        </Button>
        <Button variant="outline" size="icon" className="h-8 w-8" onClick={onPrev}>
          <SkipBack className="h-4 w-4" />
          <span className="sr-only">Previous</span>
        </Button>
        <Button variant="outline" size="icon" className="h-8 w-8" onClick={onPlay}>
          {isPlaying ? (
            <Pause className="h-4 w-4" />
          ) : (
            <Play className="h-4 w-4" />
          )}
          <span className="sr-only">{isPlaying ? 'Pause' : 'Play'}</span>
        </Button>
        <Button variant="outline" size="icon" className="h-8 w-8" onClick={onNext}>
          <SkipForward className="h-4 w-4" />
          <span className="sr-only">Next</span>
        </Button>
        <Button variant="outline" size="icon" className="h-8 w-8" onClick={onEnd}>
          <ChevronsRight className="h-4 w-4" />
          <span className="sr-only">End</span>
        </Button>
      </div>

      {/* Move counter */}
      <p className="font-mono text-[10px] text-gray-500">
        Round {currentRound + 1} / {totalRounds}
      </p>
    </div>
  );
} 
