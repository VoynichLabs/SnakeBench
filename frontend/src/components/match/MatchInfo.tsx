"use client"

interface MatchInfoProps {
  modelNames: string[];
  date: string;
  time: string;
}

export default function MatchInfo({ modelNames, date, time }: MatchInfoProps) {
  return (
    <>
      {/* Title */}
      <div className="text-center mb-6">
        <h1 className="hidden sm:block font-press-start text-base sm:text-xl md:text-2xl text-gray-800 leading-tight">
          {modelNames.join(' vs ')}
        </h1>
        <p className="font-mono text-[10px] sm:text-xs text-gray-500 italic mt-2">
          Match run on {date} at {time}
        </p>
      </div>
    </>
  )
} 
