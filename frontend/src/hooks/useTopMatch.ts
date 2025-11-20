"use client";

import { useEffect, useState } from "react";

type TopMatchResponse = {
  game_id?: string;
  total_apples?: number;
};

const API_BASE_URL = process.env.NEXT_PUBLIC_FLASK_URL || "http://127.0.0.1:5000";
const FALLBACK_MATCH_ID = process.env.NEXT_PUBLIC_TOP_MATCH_ID || null;

export function useTopMatch() {
  const [topMatchId, setTopMatchId] = useState<string | null>(FALLBACK_MATCH_ID);
  const [totalApples, setTotalApples] = useState<number | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    const fetchTopMatch = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/matches/top-apples`, {
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`Top match request failed (${response.status})`);
        }

        const data: TopMatchResponse = await response.json();

        if (controller.signal.aborted) return;

        if (data.game_id) {
          setTopMatchId(data.game_id);
        }
        if (typeof data.total_apples === "number") {
          setTotalApples(data.total_apples);
        }
      } catch (error) {
        if (controller.signal.aborted) return;
        console.error("Failed to load top match", error);
      }
    };

    fetchTopMatch();

    return () => controller.abort();
  }, []);

  const href = topMatchId ? `/match/${topMatchId}` : "/live-games";

  return {
    href,
    topMatchId,
    totalApples,
  };
}
