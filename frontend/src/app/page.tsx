import LeaderboardSection from "@/components/home/LeaderboardSection";

// Force dynamic rendering - leaderboard data changes frequently
export const dynamic = 'force-dynamic';

export default function LandingPage() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
      <LeaderboardSection />
    </div>
  );
}