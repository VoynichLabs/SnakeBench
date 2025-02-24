'use client';

interface GameControlsProps {
  currentRound: number;
  totalRounds: number;
  isPlaying: boolean;
  playbackSpeed: number;
  onPlay: () => void;
  onSpeedChange: (speed: number) => void;
  onRoundChange: (round: number) => void;
}

export default function GameControls({
  currentRound,
  totalRounds,
  isPlaying,
  playbackSpeed,
  onPlay,
  onSpeedChange,
  onRoundChange,
}: GameControlsProps) {
  return (
    <div className="mt-4 flex flex-col gap-4">
      {/* Progress Bar */}
      <div className="flex items-center gap-2">
        <input
          type="range"
          min={0}
          max={totalRounds - 1}
          value={currentRound}
          onChange={(e) => onRoundChange(Number(e.target.value))}
          className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer"
        />
        <span className="text-sm w-16 text-center">
          {currentRound + 1}/{totalRounds}
        </span>
      </div>

      {/* Controls */}
      <div className="flex justify-center items-center gap-4">
        <button
          onClick={() => onRoundChange(0)}
          className="p-2 hover:bg-gray-700 rounded"
        >
          ⏮️
        </button>
        <button
          onClick={() => onRoundChange(Math.max(0, currentRound - 1))}
          className="p-2 hover:bg-gray-700 rounded"
        >
          ⏪
        </button>
        <button
          onClick={onPlay}
          className="p-2 hover:bg-gray-700 rounded text-2xl"
        >
          {isPlaying ? "⏸️" : "▶️"}
        </button>
        <button
          onClick={() => onRoundChange(Math.min(totalRounds - 1, currentRound + 1))}
          className="p-2 hover:bg-gray-700 rounded"
        >
          ⏩
        </button>
        <button
          onClick={() => onRoundChange(totalRounds - 1)}
          className="p-2 hover:bg-gray-700 rounded"
        >
          ⏭️
        </button>

        {/* Playback Speed */}
        <select
          value={playbackSpeed}
          onChange={(e) => onSpeedChange(Number(e.target.value))}
          className="bg-gray-700 rounded px-2 py-1 text-sm"
        >
          <option value={0.5}>0.5x</option>
          <option value={1}>1x</option>
          <option value={2}>2x</option>
          <option value={4}>4x</option>
        </select>
      </div>
    </div>
  );
} 