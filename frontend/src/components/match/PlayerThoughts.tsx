"use client"

import { useRef, useEffect } from "react"

interface PlayerThoughtsProps {
  modelName: string;
  thoughts: string[];
  score: number;
  isAlive: boolean;
  color: string;
  colorScheme: {
    border: string;
    shadow: string;
    title_background: string;
  };
}

export default function PlayerThoughts({ 
  modelName, 
  thoughts, 
  score, 
  isAlive, 
  color,
  colorScheme 
}: PlayerThoughtsProps) {
  const thoughtsRef = useRef<HTMLDivElement>(null);
  
  // Auto-scroll to the bottom when thoughts update
  useEffect(() => {
    if (thoughtsRef.current) {
      thoughtsRef.current.scrollTop = thoughtsRef.current.scrollHeight;
    }
  }, [thoughts]);
  
  // Format thoughts to highlight tool usage
  const formattedThoughts = thoughts.map(thought => {
    if (thought.includes("Using tool:") || thought.includes("tool:")) {
      return { text: thought, isToolUsage: true };
    }
    return { text: thought, isToolUsage: false };
  });

  return (
    <div className={`h-[320px] sm:h-[400px] bg-white rounded-lg border ${colorScheme.border} ${colorScheme.shadow} overflow-hidden`}>
      <div className="h-full flex flex-col">
        <div className={`hidden lg:block p-3 border-b border-gray-100 backdrop-blur-sm sticky top-0 z-10 text-center ${colorScheme.title_background} bg-opacity-80`}>
          <h2 className="font-mono leading-none text-sm text-white px-2 py-1 inline-block rounded">
            {modelName}
          </h2>
        </div>
        <div className="flex-1 p-4 overflow-auto">
          <div
            ref={thoughtsRef}
            className="font-mono text-[10px] leading-[1.15] tracking-[-0.01em] text-gray-800 space-y-1"
          >
            {formattedThoughts.map((thought, i) => 
              thought.isToolUsage ? (
                <div
                  key={i}
                  className="bg-[#3B2F1D] text-[#FFA940] px-2 py-1 font-mono text-[10px] leading-none my-1"
                >
                  {thought.text}
                </div>
              ) : (
                <p key={i} className="leading-tight">
                  {thought.text}
                </p>
              )
            )}
          </div>
        </div>
        <div className="p-3 border-t border-gray-100 flex justify-between items-center">
          <div className="flex items-center gap-2 text-blue-500 font-mono leading-none text-[10px]">
            {isAlive ? (
              <>
              </>
            ) : (
              <span className="text-red-500 font-bold text-sm">&lt;Eliminated&gt;</span>
            )}
          </div>
          <div className={`flex items-center gap-1 font-mono text-[15px] ${color === "player1" ? "justify-start" : "justify-end"} ${color === "player1" ? "order-first" : "order-last"}`}>
            {color === "player1" ? (
              <>
                {/* Always show score number */}
                <span className="text-gray-400 mr-1">{score}</span>
                {/* Green apples for tens (left side for player1) */}
                {Array.from({ length: Math.floor(score / 10) }).map((_, i) => (
                  <span key={`green-${i}`} className="text-green-500">🍏</span>
                ))}
                {/* Red apples for ones */}
                {Array.from({ length: score % 10 }).map((_, i) => (
                  <span key={`red-${i}`} className="text-red-500">🍎</span>
                ))}
              </>
            ) : (
              <>
                {/* Red apples for ones */}
                {Array.from({ length: score % 10 }).map((_, i) => (
                  <span key={`red-${i}`} className="text-red-500">🍎</span>
                ))}
                {/* Green apples for tens (right side for player2) */}
                {Array.from({ length: Math.floor(score / 10) }).map((_, i) => (
                  <span key={`green-${i}`} className="text-green-500">🍏</span>
                ))}
                {/* Always show score number */}
                <span className="text-gray-400 ml-1">{score}</span>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
} 
