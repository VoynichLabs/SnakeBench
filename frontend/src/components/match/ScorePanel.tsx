'use client';

import { useState } from 'react';
import Modal from './Modal';

interface GameRound {
  round_number: number;
  move_history?: {
    [modelId: string]: {
      move: string;
      rationale: string;
    };
  }[];
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

interface ScorePanelProps {
  metadata: {
    models: Record<string, string>;
    game_result: Record<string, string>;
    final_scores: Record<string, number>;
    death_info: Record<string, { reason: string; round: number }>;
  };
  currentRound: GameRound;
  nextMoves?: {
    [modelId: string]: {
      move: string;
      rationale: string;
    };
  };
}

export default function ScorePanel({ metadata, currentRound, nextMoves }: ScorePanelProps) {
  const [modalContent, setModalContent] = useState<{
    isOpen: boolean;
    title: string;
    content: string;
  }>({
    isOpen: false,
    title: '',
    content: ''
  });

  const renderPlayerInfo = (playerId: string) => {
    const isAlive = currentRound.alive[playerId];
    const score = currentRound.scores[playerId];
    const modelName = metadata.models[playerId];
    const deathInfo = metadata.death_info[playerId];
    const justDied = deathInfo?.round === currentRound.round_number;

    const upcomingMove = nextMoves?.[playerId];
    
    const bgColor = playerId === '1' ? 'bg-green-900' : 'bg-blue-900';
    const borderColor = playerId === '1' ? 'border-green-500' : 'border-blue-500';

    return (
      <div className={`${bgColor} border-2 ${borderColor} rounded-lg p-4 mb-4`}>
        <div className="flex justify-between items-center mb-2">
          <h3 className="text-lg font-bold">{modelName}</h3>
          <div className="flex items-center gap-2">
            <span className={`w-3 h-3 rounded-full ${isAlive ? 'bg-green-500' : 'bg-red-500'}`} />
            <span className="text-sm">{isAlive ? 'Active' : 'Dead'}</span>
          </div>
        </div>
        
        <div className="mb-2">
          <span className="text-gray-400">Score: </span>
          <span className="text-xl font-bold">{score}</span>
        </div>

        {justDied && (
          <div className="text-red-400 text-sm mb-2 animate-fade-in">
            Died from: {deathInfo.reason}
          </div>
        )}

        {upcomingMove && isAlive && (
          <div className="mt-4">
            <div className="flex justify-between items-center text-sm text-gray-400 mb-1">
              <span>Next Move: {upcomingMove.move}</span>
              <button
                onClick={() => setModalContent({
                  isOpen: true,
                  title: `${modelName}'s Next Move`,
                  content: upcomingMove.rationale
                })}
                className="px-2 py-1 bg-gray-700 hover:bg-gray-600 rounded text-xs"
              >
                Expand
              </button>
            </div>
            <div className="text-sm bg-black bg-opacity-30 p-2 rounded max-h-32 overflow-y-auto">
              {upcomingMove.rationale}
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <>
      <div className="bg-gray-800 rounded-lg p-6">
        <h2 className="text-xl font-bold mb-4">Game Stats</h2>
        {renderPlayerInfo('1')}
        {renderPlayerInfo('2')}
      </div>

      <Modal
        isOpen={modalContent.isOpen}
        onClose={() => setModalContent(prev => ({ ...prev, isOpen: false }))}
        title={modalContent.title}
      >
        <div className="whitespace-pre-wrap">
          {modalContent.content}
        </div>
      </Modal>
    </>
  );
} 