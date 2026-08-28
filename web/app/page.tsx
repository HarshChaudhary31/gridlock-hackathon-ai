"use client";

import { ChangeEvent, useEffect, useState } from "react";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "https://gridlock-hackathon-ai.onrender.com";

type VehicleBreakdown = {
  total?: number;
  cars?: number;
  bikes?: number;
  buses?: number;
  trucks?: number;
  autos?: number;
  [key: string]: number | undefined;
};

type LatestResult = {
  vehicle_counts?: VehicleBreakdown;
  congestion?: {
    avg_speed?: number;
    level?: string;
    score?: number;
  };
  violations?: unknown[];
};

type AnalyticsSummary = {
  total_vehicles_detected?: number;
  violations_count?: number;
  avg_congestion_score?: number;
  vehicle_breakdown?: VehicleBreakdown;
};

type StatusResponse = {
  session_id: string;
  status: string;
  result?: {
    latest?: LatestResult;
  };
  latest?: LatestResult;
};

type UploadResponse = {
  session_id: string;
  status: string;
  message?: string;
};

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [sessionId, setSessionId] = useState("");
  const [status, setStatus] = useState("Select a traffic video to begin.");
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState("");

  const [latest, setLatest] = useState<LatestResult>({});
  const [summary, setSummary] = useState<AnalyticsSummary>({});

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const selected = event.target.files?.[0] || null;
    setFile(selected);
    setError("");
    setStatus(
      selected
        ? `Selected: ${selected.name}`
        : "Select a traffic video to begin."
    );
  };

  const uploadVideo = async () => {
    if (!file) {
      setError("Please select a video first.");
      return;
    }

    setProcessing(true);
    setError("");
    setLatest({});
    setSummary({});
    setSessionId("");
    setStatus("Uploading video...");

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(
        `${API_BASE}/api/v1/video/upload?frame_skip=5&save_output=false&max_frames=150`,
        {
          method: "POST",
          body: formData,
        }
      );

      if (!response.ok) {
        const text = await response.text();
        throw new Error(
          `Upload failed (${response.status}): ${text || response.statusText}`
        );
      }

      const data: UploadResponse = await response.json();

      if (!data.session_id) {
        throw new Error("Backend did not return a session_id.");
      }

      setSessionId(data.session_id);
      setStatus("Video uploaded. AI processing started.");
    } catch (err) {
      setProcessing(false);
      setError(err instanceof Error ? err.message : "Upload failed.");
      setStatus("Processing failed.");
    }
  };

  useEffect(() => {
    if (!sessionId) return;

    let stopped = false;

    const poll = async () => {
      try {
        const response = await fetch(
          `${API_BASE}/api/v1/video/status/${sessionId}`,
          { cache: "no-store" }
        );

        if (!response.ok) {
          const text = await response.text();
          throw new Error(
            `Status request failed (${response.status}): ${
              text || response.statusText
            }`
          );
        }

        const data: StatusResponse = await response.json();

        const currentLatest = data.latest || data.result?.latest || {};
        setLatest(currentLatest);

        if (data.status === "completed") {
          setStatus("Processing completed. Loading analytics...");

          const summaryResponse = await fetch(
            `${API_BASE}/api/v1/analytics/summary/${sessionId}`,
            { cache: "no-store" }
          );

          if (!summaryResponse.ok) {
            const text = await summaryResponse.text();
            throw new Error(
              `Analytics request failed (${summaryResponse.status}): ${
                text || summaryResponse.statusText
              }`
            );
          }

          const summaryData: AnalyticsSummary =
            await summaryResponse.json();

          setSummary(summaryData);
          setProcessing(false);
          setStatus("Analysis completed.");
          return;
        }

        if (data.status === "failed" || data.status === "error") {
          throw new Error("The backend failed while processing the video.");
        }

        setStatus(`AI processing: ${data.status || "processing"}...`);

        if (!stopped) {
          window.setTimeout(poll, 3000);
        }
      } catch (err) {
        if (!stopped) {
          setProcessing(false);
          setError(
            err instanceof Error ? err.message : "Unable to read processing status."
          );
          setStatus("Processing failed.");
        }
      }
    };

    poll();

    return () => {
      stopped = true;
    };
  }, [sessionId]);

  const vehicles = {
    ...(latest.vehicle_counts || {}),
    ...(summary.vehicle_breakdown || {}),
  };

  const totalVehicles =
    summary.total_vehicles_detected ??
    vehicles.total ??
    0;

  const averageSpeed = latest.congestion?.avg_speed;

  const violationsCount =
    summary.violations_count ??
    latest.violations?.length ??
    0;

  const hasVehicleData =
    Object.keys(latest.vehicle_counts || {}).length > 0 ||
    Object.keys(summary.vehicle_breakdown || {}).length > 0;

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <div className="mx-auto max-w-6xl px-6 py-10">
        <header className="mb-8">
          <p className="text-sm font-semibold uppercase tracking-[0.25em] text-cyan-400">
            Smart Traffic Monitoring
          </p>
          <h1 className="mt-2 text-4xl font-bold">
            Traffic AI Dashboard
          </h1>
          <p className="mt-2 text-slate-400">
            Upload a traffic video and view real AI detection results.
          </p>
        </header>

        <section className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
          <h2 className="text-xl font-semibold">Analyze Traffic Video</h2>

          <div className="mt-5 flex flex-col gap-4 sm:flex-row sm:items-center">
            <input
              type="file"
              accept="video/*"
              onChange={handleFileChange}
              className="block w-full rounded-lg border border-slate-700 bg-slate-950 p-3 text-sm text-slate-300"
            />

            <button
              onClick={uploadVideo}
              disabled={!file || processing}
              className="rounded-lg bg-cyan-500 px-6 py-3 font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {processing ? "Processing..." : "Analyze Video"}
            </button>
          </div>

          <p className="mt-4 text-sm text-slate-400">{status}</p>

          {sessionId && (
            <p className="mt-1 break-all text-xs text-slate-500">
              Session: {sessionId}
            </p>
          )}

          {error && (
            <div className="mt-4 rounded-lg border border-red-800 bg-red-950/40 p-4 text-sm text-red-300">
              {error}
            </div>
          )}
        </section>

        <section className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            title="Total Vehicles"
            value={hasVehicleData ? totalVehicles : "—"}
          />

          <MetricCard
            title="Average Speed"
            value={
              averageSpeed !== undefined
                ? `${Number(averageSpeed).toFixed(1)} km/h`
                : "—"
            }
          />

          <MetricCard
            title="Violations"
            value={sessionId ? violationsCount : "—"}
          />

          <MetricCard
            title="Congestion"
            value={latest.congestion?.level || "—"}
          />
        </section>

        <section className="mt-8">
          <h2 className="mb-4 text-2xl font-bold">Vehicle Statistics</h2>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            <StatCard title="Cars" value={vehicles.cars} />
            <StatCard title="Bikes" value={vehicles.bikes} />
            <StatCard title="Autos" value={vehicles.autos} />
            <StatCard title="Buses" value={vehicles.buses} />
            <StatCard title="Trucks" value={vehicles.trucks} />
          </div>
        </section>

        <section className="mt-8 grid gap-6 lg:grid-cols-2">
          <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
            <h2 className="text-xl font-bold">Speed</h2>

            <div className="mt-5">
              <p className="text-sm text-slate-400">Average detected speed</p>
              <p className="mt-1 text-4xl font-bold">
                {averageSpeed !== undefined
                  ? `${Number(averageSpeed).toFixed(1)} km/h`
                  : "—"}
              </p>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
            <h2 className="text-xl font-bold">Helmet Detection</h2>

            <p className="mt-5 text-sm text-slate-400">
              Helmet-specific statistics will appear here when the backend
              returns helmet detection data.
            </p>

            <div className="mt-4 rounded-lg bg-slate-950 p-4 text-sm text-slate-500">
              No helmet detection fields were returned by the tested backend
              response.
            </div>
          </div>
        </section>

        <section className="mt-8 rounded-2xl border border-slate-800 bg-slate-900 p-6">
          <h2 className="text-xl font-bold">Violations</h2>

          {violationsCount > 0 ? (
            <p className="mt-4 text-slate-300">
              {violationsCount} violation(s) detected.
            </p>
          ) : (
            <p className="mt-4 text-slate-500">
              No violations were returned by the backend for this analysis.
            </p>
          )}
        </section>
      </div>
    </main>
  );
}

function MetricCard({
  title,
  value,
}: {
  title: string;
  value: string | number;
}) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
      <p className="text-sm text-slate-400">{title}</p>
      <p className="mt-2 text-2xl font-bold">{value}</p>
    </div>
  );
}

function StatCard({
  title,
  value,
}: {
  title: string;
  value?: number;
}) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
      <p className="text-sm text-slate-400">{title}</p>
      <p className="mt-2 text-3xl font-bold">{value ?? "—"}</p>
    </div>
  );
}
