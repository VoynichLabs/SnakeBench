"use client"

import Link from "next/link"

interface MatchInfoProps {
  modelNames: string[];
  date: string;
  time: string;
}

export default function MatchInfo({ modelNames, date, time }: MatchInfoProps) {
  return (
    <div className="mb-4 flex items-center justify-between gap-4">
      <Link
        href="/"
        className="font-mono text-xs text-gray-400 hover:text-gray-600 transition-colors"
      >
        ← Leaderboard
      </Link>
      <p className="font-mono text-[10px] text-gray-400">
        {date} at {time}
      </p>
    </div>
  )
} 
