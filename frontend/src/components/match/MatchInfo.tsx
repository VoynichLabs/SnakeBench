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
        <h1 className="font-press-start text-lg text-gray-800">{modelNames.join(' vs ')}</h1>
        <p className="font-mono text-[10px] text-gray-500 italic mt-2">
          Match run on {date} at {time}
        </p>
      </div>
    </>
  )
} 
