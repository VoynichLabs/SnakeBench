"use client";

import { useState, useEffect, useRef } from "react";
import { createClient } from "@/lib/supabase/client";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_FLASK_URL || "http://127.0.0.1:5000";

interface Model {
  name: string;
  is_active: boolean;
  provider: string;
}

function ModelSearchSelect({
  models,
  value,
  onChange,
  placeholder = "Search models...",
}: {
  models: Model[];
  value: string;
  onChange: (name: string) => void;
  placeholder?: string;
}) {
  const [query, setQuery] = useState(value);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Sync display text when value is cleared externally
  useEffect(() => {
    if (!value) setQuery("");
  }, [value]);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
        // Reset query to selected value if user didn't pick anything
        if (!value) setQuery("");
        else setQuery(value);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [value]);

  const filtered = models.filter((m) =>
    m.name.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <div ref={ref} className="relative">
      <div className="flex items-center">
        <input
          type="text"
          value={query}
          placeholder={placeholder}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
            if (!e.target.value) onChange("");
          }}
          onFocus={() => setOpen(true)}
          className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:border-zinc-500"
        />
        {value && (
          <button
            type="button"
            onClick={() => {
              onChange("");
              setQuery("");
              setOpen(false);
            }}
            className="absolute right-2 text-zinc-500 hover:text-zinc-300 text-lg leading-none"
            aria-label="Clear selection"
          >
            &times;
          </button>
        )}
      </div>

      {open && filtered.length > 0 && (
        <ul className="absolute z-50 mt-1 w-full max-h-60 overflow-y-auto bg-zinc-800 border border-zinc-700 rounded-lg shadow-lg">
          {filtered.map((m) => (
            <li
              key={m.name}
              onClick={() => {
                onChange(m.name);
                setQuery(m.name);
                setOpen(false);
              }}
              className={`px-3 py-2 cursor-pointer hover:bg-zinc-700 text-sm ${
                m.name === value ? "text-green-400" : "text-white"
              }`}
            >
              {m.name}
              <span className="ml-2 text-zinc-500 text-xs">{m.provider}</span>
            </li>
          ))}
        </ul>
      )}

      {open && query && filtered.length === 0 && (
        <div className="absolute z-50 mt-1 w-full bg-zinc-800 border border-zinc-700 rounded-lg shadow-lg px-3 py-2 text-zinc-500 text-sm">
          No models found
        </div>
      )}
    </div>
  );
}

export default function MatchupPicker() {
  const [models, setModels] = useState<Model[]>([]);
  const [modelA, setModelA] = useState("");
  const [modelB, setModelB] = useState("");
  const [numGames, setNumGames] = useState(1);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);

  useEffect(() => {
    async function fetchModels() {
      try {
        const res = await fetch(`${API_BASE_URL}/api/models`);
        const data = await res.json();
        if (data.models) {
          setModels(data.models);
        }
      } catch (err) {
        console.error("Failed to fetch models:", err);
      }
    }
    fetchModels();
  }, []);

  const handleDispatch = async () => {
    if (!modelA || !modelB) {
      setResult({ type: "error", message: "Please select both models." });
      return;
    }

    setLoading(true);
    setResult(null);

    try {
      const supabase = createClient();
      const {
        data: { session },
      } = await supabase.auth.getSession();

      if (!session) {
        setResult({ type: "error", message: "Not authenticated." });
        setLoading(false);
        return;
      }

      const res = await fetch(`${API_BASE_URL}/api/admin/dispatch`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.access_token}`,
        },
        body: JSON.stringify({
          model_a: modelA,
          model_b: modelB,
          num_games: numGames,
          game_params: {
            width: 10,
            height: 10,
            max_rounds: 100,
            num_apples: 5,
          },
        }),
      });

      const data = await res.json();

      if (res.ok) {
        setResult({
          type: "success",
          message: `Dispatched ${data.tasks_queued} game(s). Batch: ${data.batch_id}`,
        });
      } else {
        setResult({
          type: "error",
          message: data.error || "Dispatch failed.",
        });
      }
    } catch (err) {
      setResult({
        type: "error",
        message: `Network error: ${err instanceof Error ? err.message : "Unknown error"}`,
      });
    } finally {
      setLoading(false);
    }
  };

  const activeModels = models.filter((m) => m.is_active);

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-white">Dispatch Games</h2>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm text-zinc-400 mb-1">Model A</label>
          <ModelSearchSelect
            models={activeModels}
            value={modelA}
            onChange={setModelA}
            placeholder="Search models..."
          />
        </div>

        <div>
          <label className="block text-sm text-zinc-400 mb-1">Model B</label>
          <ModelSearchSelect
            models={activeModels}
            value={modelB}
            onChange={setModelB}
            placeholder="Search models..."
          />
        </div>
      </div>

      <div>
        <label className="block text-sm text-zinc-400 mb-1">
          Number of games (1-50)
        </label>
        <input
          type="number"
          min={1}
          max={50}
          value={numGames}
          onChange={(e) =>
            setNumGames(Math.min(50, Math.max(1, parseInt(e.target.value) || 1)))
          }
          className="w-32 px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white"
        />
      </div>

      <button
        onClick={handleDispatch}
        disabled={loading || !modelA || !modelB}
        className="px-6 py-3 bg-green-600 hover:bg-green-500 disabled:bg-zinc-700 disabled:text-zinc-500 text-white rounded-lg font-medium transition-colors"
      >
        {loading ? "Dispatching..." : "Start Games"}
      </button>

      {result && (
        <div
          className={`p-4 rounded-lg ${
            result.type === "success"
              ? "bg-green-900/50 border border-green-700 text-green-300"
              : "bg-red-900/50 border border-red-700 text-red-300"
          }`}
        >
          {result.message}
        </div>
      )}
    </div>
  );
}
