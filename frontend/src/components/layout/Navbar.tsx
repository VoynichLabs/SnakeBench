import Link from "next/link";

export default function Navbar() {
  return (
    <nav className="bg-white border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex">
            <div className="flex-shrink-0 flex items-center">
              <Link href="/" className="inline-flex items-baseline text-2xl font-press-start text-gray-900">
                <span className="relative -top-1 text-3xl mr-2">🐍</span>
                <span>SnakeBench</span>
              </Link>
            </div>
            <div className="hidden sm:ml-6 sm:flex sm:space-x-8">
              <Link
                href="/live-games"
                className="border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-mono"
              >
                🔴 Live Games
              </Link>
              <Link
                href={`/match/${process.env.NEXT_PUBLIC_TOP_MATCH_ID}`}
                className="border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-mono"
              >
                Top Match
              </Link>
              <Link
                href="/about"
                className="border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-mono"
              >
                About
              </Link>
            </div>
          </div>
        </div>
      </div>
    </nav>
  );
} 