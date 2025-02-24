'use client';

import { useState, useEffect } from 'react';
import AsciiSnakePlayer from '@/components/AsciiSnakePlayer2';

interface MoveHistoryEntry {
  [modelId: string]: {
    move: string;
    rationale: string;
  };
}

interface RoundData {
  round_number: number;
  move_history?: MoveHistoryEntry[];
  snake_positions: {
    [key: string]: [number, number][];
  };
  alive: {
    [key: string]: boolean;
  };
  scores: {
    [key: string]: number;
  };
  width: number;
  height: number;
  apples: [number, number][];
}

interface GameData {
  metadata: {
    game_id: string;
    models: Record<string, string>;
    game_result: Record<string, string>;
    death_info: Record<string, { reason: string }>;
  };
  rounds: RoundData[];
}

interface GameViewerProps {
  gameData: GameData;
  isLarge?: boolean;
}

/**
 * GameViewer displays:
 *  - The ASCII snake board at the top (via AsciiSnakePlayer)
 *  - Next/Back/Play controls
 *  - Two columns with model #1 and model #2 info
 *  - Rationales for the current round
 */
export default function GameViewer({ gameData, isLarge = false }: GameViewerProps) {
  const { rounds, metadata } = gameData;
  
  // Current index in the rounds array
  const [currentRoundIndex, setCurrentRoundIndex] = useState(0);
  // Whether auto-play is active
  const [isPlaying, setIsPlaying] = useState(false);

  // We'll keep a simple useEffect to handle auto-play
  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | null = null;
    if (isPlaying) {
      interval = setInterval(() => {
        setCurrentRoundIndex((prev) => {
          // Advance one round if possible, else stop
          if (prev < rounds.length - 1) {
            return prev + 1;
          } else {
            setIsPlaying(false);
            return prev;
          }
        });
      }, parseInt(process.env.NEXT_PUBLIC_ANIMATION_SPEED || '750')); // 1 second per move (adjust as needed)
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isPlaying, rounds.length]);

  // Handlers for back/forward
  const handleBack = () => {
    setIsPlaying(false);
    setCurrentRoundIndex((prev) => Math.max(prev - 1, 0));
  };

  const handleForward = () => {
    setIsPlaying(false);
    setCurrentRoundIndex((prev) => Math.min(prev + 1, rounds.length - 1));
  };

  const handlePlayPause = () => {
    setIsPlaying((prev) => !prev);
  };

 
  // Get the CURRENT round's move history (instead of next round)
  const currentRound = rounds[currentRoundIndex];
  const currentMoveHistory = currentRound.move_history || [];
  // We want the last move in that history
  const lastMove = currentMoveHistory[currentMoveHistory.length - 1] || {};

  const modelOneId = '1';
  const modelTwoId = '2';
  const modelOneName = metadata.models[modelOneId];
  const modelTwoName = metadata.models[modelTwoId];

  // Extract rationale/move for each model from the CURRENT round
  const modelOneRationale = lastMove[modelOneId]?.rationale || 'No move available';
  const modelTwoRationale = lastMove[modelTwoId]?.rationale || 'No move available';
  const modelOneChoice = lastMove[modelOneId]?.move || 'No move available';
  const modelTwoChoice = lastMove[modelTwoId]?.move || 'No move available';

  // Add helper function to get game outcome message
  const getGameOutcomeMessage = () => {
    const { game_result, death_info } = metadata;
    const messages = [];

    for (const [modelId, result] of Object.entries(game_result)) {
      const modelName = metadata.models[modelId];
      const resultText = result === 'won' ? 'Winner' : 'Lost';
      let message = `${modelName}: ${resultText}`;
      
      // Add death reason if available
      if (death_info?.[modelId]) {
        message += ` (${death_info[modelId].reason})`;
      }
      
      messages.push(message);
    }

    return messages;
  };

  return (
    <div className={`container mx-auto px-4 ${isLarge ? 'max-w-7xl' : 'max-w-6xl'}`}>
      {/* Game outcome banner - show only when game is finished */}
      {currentRoundIndex === rounds.length - 1 && (
        <div className="p-4 mb-4 rounded text-center">
          <h2 className="text-xl font-bold mb-2">Game Over</h2>
          {getGameOutcomeMessage().map((message, index) => (
            <div key={index} className="text-lg">
              {message}
            </div>
          ))}
        </div>
      )}

      {/* The ASCII snake board for the current round (rendered by the child) */}
      <div className={`flex justify-center ${isLarge ? 'scale-125' : ''}`}>
        <AsciiSnakePlayer
          rounds={rounds}           // pass all rounds
          metadata={metadata}       // pass metadata for model names, etc.
          currentRoundIndex={currentRoundIndex}
        />
      </div>

      {/* Instructions */}
      <p className="text-center text-gray-500 italic text-sm mt-2 mb-1 pt-8">
        Click &quot;play&quot; to watch the game play out automatically. Otherwise, use the controls below to navigate through the game rounds and view the LLM rationale.
      </p>

      {/* Controls */}
      <div className="flex justify-center gap-4 my-4">
        <button onClick={handleBack}>Back</button>
        <button onClick={handlePlayPause}>
          {isPlaying ? 'Pause' : 'Play'}
        </button>
        <button onClick={handleForward}>Forward</button>
      </div>

      {/* Rationales */}
      <div className="border border-gray-300 p-4 rounded max-w-4xl mx-auto">
        <h3 className="text-center pb-2">Round {currentRoundIndex}:</h3>
        <div className="grid grid-cols-2 gap-5">
          <div className="text-[10px] sm:text-xs">
            <h4>Model #1: {modelOneName}</h4>
            <strong>Choice: {modelOneChoice}</strong>
            <br />
            <strong>Rationale:</strong>
            <p className="whitespace-pre-wrap">{modelOneRationale}</p>
          </div>
          <div className="text-[10px] sm:text-xs">
            <h4>Model #2: {modelTwoName}</h4>
            <strong>Choice: {modelTwoChoice}</strong>
            <br />
            <strong>Rationale:</strong>
            <p className="whitespace-pre-wrap">{modelTwoRationale}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
