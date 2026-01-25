"use client"

import { useRef, useEffect } from "react"
import { Skull } from "lucide-react"

interface PlayerThoughtsProps {
  modelName: string;
  thoughts: string[];
  score: number;
  isAlive: boolean;
  color: string;
  colorScheme: {
    main?: string;
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
    <div className="h-[320px] sm:h-[400px] bg-white rounded-lg border border-gray-200 overflow-hidden shadow-sm">
      <div className="h-full flex flex-col">
        {/* Header with model name */}
        <div className={`hidden lg:flex items-center justify-between p-2.5 border-b border-gray-100 ${colorScheme.title_background}`}>
          <h2 className="font-mono text-xs text-white truncate" title={modelName}>
            {modelName}
          </h2>
          {!isAlive && <Skull className="w-3.5 h-3.5 text-white/70 flex-shrink-0" />}
        </div>

        {/* Thoughts content */}
        <div className="flex-1 p-3 overflow-auto bg-gray-50">
          <div
            ref={thoughtsRef}
            className="font-mono text-[10px] leading-relaxed text-gray-700 space-y-1.5"
          >
            {formattedThoughts.map((thought, i) =>
              thought.isToolUsage ? (
                <div
                  key={i}
                  className="bg-amber-100 text-amber-800 px-2 py-1 rounded text-[9px]"
                >
                  {thought.text}
                </div>
              ) : (
                <p key={i}>
                  {thought.text}
                </p>
              )
            )}
          </div>
        </div>

        {/* Footer with score */}
        <div className="p-2.5 border-t border-gray-100 bg-white">
          <div className={`flex items-center gap-1.5 font-mono text-sm ${color === "player1" ? "justify-start" : "justify-end"}`}>
            {color === "player1" ? (
              <>
                <span className="text-gray-900 font-medium">{score}</span>
                <span className="text-gray-400 text-[10px]">apples</span>
              </>
            ) : (
              <>
                <span className="text-gray-400 text-[10px]">apples</span>
                <span className="text-gray-900 font-medium">{score}</span>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
} 
