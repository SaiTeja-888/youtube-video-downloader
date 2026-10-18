"use client";

import React, { useState, useEffect } from "react";
import axios from "axios";
import { 
  ArrowLeft, 
  Activity, 
  Database, 
  HardDrive, 
  AlertOctagon, 
  FileText, 
  CheckCircle, 
  XCircle, 
  Server,
  RefreshCw
} from "lucide-react";
import Link from "next/link";

// API Base configuration
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

const playGlassSound = () => {
  try {
    const AudioContextClass =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AudioContextClass) return;

    const audioContext = new AudioContextClass();
    const now = audioContext.currentTime;
    const gain = audioContext.createGain();
    const tone = audioContext.createOscillator();

    tone.type = "sine";
    tone.frequency.setValueAtTime(720, now);
    tone.frequency.exponentialRampToValueAtTime(1180, now + 0.08);
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(0.05, now + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.16);

    tone.connect(gain);
    gain.connect(audioContext.destination);
    tone.start(now);
    tone.stop(now + 0.16);
    window.setTimeout(() => void audioContext.close(), 220);
  } catch {
    // Optional click feedback only.
  }
};

interface DailyStat {
  date: string;
  total: number;
  success: number;
  failed: number;
}

interface PlatformStat {
  platform: string;
  count: number;
}

interface HealthResponse {
  status: string;
  postgres: string;
  redis: string;
  rabbitmq: string;
}

interface StatsResponse {
  total_downloads: number;
  successful_downloads: number;
  failed_downloads: number;
  daily_stats: DailyStat[];
  platform_ratios: PlatformStat[];
  health: HealthResponse;
}

export default function AdminDashboard() {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [logs, setLogs] = useState<string>("Loading backend logs...");
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchDashboardData = async () => {
    setRefreshing(true);
    try {
      // Fetch stats
      const statsRes = await axios.get(`${API_BASE}/admin/stats`);
      setStats(statsRes.data);
      
      // Fetch logs
      const logsRes = await axios.get(`${API_BASE}/admin/logs`);
      setLogs(logsRes.data.logs || "No logs available.");
      
      setErrorMsg(null);
    } catch (err: unknown) {
      console.error(err);
      setErrorMsg("Failed to connect to backend server. Make sure services are running.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    const handle = setTimeout(() => {
      void fetchDashboardData();
    }, 0);
    
    // Auto-refresh stats every 15 seconds
    const interval = setInterval(() => {
      void fetchDashboardData();
    }, 15000);
    
    return () => {
      clearTimeout(handle);
      clearInterval(interval);
    };
  }, []);

  return (
    <div className="min-h-screen text-cyan-50 font-sans p-6 md:p-12 relative overflow-hidden">
      <div className="bg-mesh-animation" />

      <div className="max-w-7xl mx-auto space-y-8 relative">
        
        {/* Navigation / Header */}
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <div className="flex items-center space-x-3">
            <Link 
              href="/" 
              onClick={playGlassSound}
              className="p-2 glass-chip rounded-xl hover:bg-white/10 hover:text-white transition-colors"
            >
              <ArrowLeft size={16} />
            </Link>
            <div>
              <span className="text-xs font-bold text-orange-200 uppercase tracking-widest">POSTLINK media downloader</span>
              <h1 className="text-3xl font-extrabold text-white">System Admin Panel</h1>
            </div>
          </div>

          <button
            onClick={() => {
              playGlassSound();
              void fetchDashboardData();
            }}
            disabled={refreshing}
            className="px-4 py-2 glass-chip hover:bg-cyan-300/10 hover:border-cyan-300/50 rounded-xl text-xs font-bold flex items-center gap-2 cursor-pointer transition-all"
          >
            <RefreshCw className={refreshing ? "animate-spin" : ""} size={14} />
            {refreshing ? "Refreshing..." : "Force Refresh"}
          </button>
        </div>

        {errorMsg && (
          <div className="p-4 bg-orange-500/10 border border-orange-300/30 rounded-2xl text-orange-100 text-sm flex items-center gap-3 backdrop-blur-xl">
            <AlertOctagon className="shrink-0" size={18} />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* LOADING STATE */}
        {loading ? (
          <div className="py-24 text-center">
            <RefreshCw className="animate-spin mx-auto text-cyan-200 mb-4" size={32} />
            <span className="font-semibold text-cyan-100/50">Retrieving system diagnostics...</span>
          </div>
        ) : (
          stats && (
            <>
              {/* STATUS CARDS SECTION */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                
                {/* Total */}
                <div className="p-6 glass-panel rounded-2xl flex items-center justify-between">
                  <div className="space-y-1">
                    <span className="text-xs font-bold text-cyan-100/50 uppercase">Total Requests</span>
                    <p className="text-3xl font-black text-white">{stats.total_downloads.toLocaleString()}</p>
                  </div>
                  <div className="p-3 bg-cyan-300/10 text-cyan-200 rounded-xl">
                    <Activity size={24} />
                  </div>
                </div>

                {/* Successful */}
                <div className="p-6 glass-panel rounded-2xl flex items-center justify-between">
                  <div className="space-y-1">
                    <span className="text-xs font-bold text-cyan-100/50 uppercase">Success Rate</span>
                    <p className="text-3xl font-black text-cyan-200">
                      {stats.total_downloads > 0 
                        ? `${((stats.successful_downloads / stats.total_downloads) * 100).toFixed(1)}%` 
                        : "100%"
                      }
                    </p>
                  </div>
                  <div className="p-3 bg-cyan-300/10 text-cyan-200 rounded-xl">
                    <CheckCircle size={24} />
                  </div>
                </div>

                {/* Successful Raw */}
                <div className="p-6 glass-panel rounded-2xl flex items-center justify-between">
                  <div className="space-y-1">
                    <span className="text-xs font-bold text-cyan-100/50 uppercase">Completed Files</span>
                    <p className="text-3xl font-black text-white">{stats.successful_downloads.toLocaleString()}</p>
                  </div>
                  <div className="p-3 bg-orange-400/10 text-orange-200 rounded-xl">
                    <HardDrive size={24} />
                  </div>
                </div>

                {/* Failed downloads */}
                <div className="p-6 glass-panel rounded-2xl flex items-center justify-between">
                  <div className="space-y-1">
                    <span className="text-xs font-bold text-cyan-100/50 uppercase">Failed Extends</span>
                    <p className="text-3xl font-black text-orange-200">{stats.failed_downloads.toLocaleString()}</p>
                  </div>
                  <div className="p-3 bg-orange-400/10 text-orange-200 rounded-xl">
                    <XCircle size={24} />
                  </div>
                </div>

              </div>

              {/* MIDDLE SECTION: HEALTH & PLATFORMS */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                
                {/* Health Metrics */}
                <div className="p-6 glass-panel rounded-2xl md:col-span-1 space-y-6">
                  <h3 className="text-md font-bold text-white border-b border-white/10 pb-2 flex items-center gap-2">
                    <Server size={18} className="text-cyan-200" />
                    Container Health Check
                  </h3>
                  
                  <div className="space-y-4 font-semibold text-sm">
                    {/* Database */}
                    <div className="flex items-center justify-between">
                      <span className="text-cyan-100/60">PostgreSQL Database</span>
                      <span className={`px-2 py-0.5 rounded-full text-xs font-bold uppercase ${stats.health.postgres === 'healthy' ? 'bg-cyan-300/10 text-cyan-100' : 'bg-orange-500/10 text-orange-200'}`}>
                        {stats.health.postgres}
                      </span>
                    </div>

                    {/* Redis */}
                    <div className="flex items-center justify-between">
                      <span className="text-cyan-100/60">Redis Cache & Rate-limit</span>
                      <span className={`px-2 py-0.5 rounded-full text-xs font-bold uppercase ${stats.health.redis === 'healthy' ? 'bg-cyan-300/10 text-cyan-100' : 'bg-orange-500/10 text-orange-200'}`}>
                        {stats.health.redis}
                      </span>
                    </div>

                    {/* RabbitMQ */}
                    <div className="flex items-center justify-between">
                      <span className="text-cyan-100/60">Celery RabbitMQ Broker</span>
                      <span className={`px-2 py-0.5 rounded-full text-xs font-bold uppercase ${stats.health.rabbitmq === 'healthy' ? 'bg-cyan-300/10 text-cyan-100' : 'bg-orange-500/10 text-orange-200'}`}>
                        {stats.health.rabbitmq}
                      </span>
                    </div>

                    {/* Server status */}
                    <div className="flex items-center justify-between border-t border-white/10 pt-3">
                      <span className="text-cyan-100/60">Overall Status</span>
                      <span className={`px-3 py-1 rounded-full text-xs font-black uppercase ${stats.health.status === 'healthy' ? 'bg-cyan-300/20 text-cyan-100' : 'bg-orange-500/20 text-orange-200'}`}>
                        {stats.health.status}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Popular Platforms */}
                <div className="p-6 glass-panel rounded-2xl md:col-span-2 space-y-6">
                  <h3 className="text-md font-bold text-white border-b border-white/10 pb-2 flex items-center gap-2">
                    <Database size={18} className="text-orange-200" />
                    Popular Extractors (Volume)
                  </h3>

                  {stats.platform_ratios.length === 0 ? (
                    <div className="py-12 text-center text-cyan-100/45 text-xs font-semibold">
                      No downloads recorded yet.
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {stats.platform_ratios.map((item, idx) => {
                        const percent = stats.total_downloads > 0 
                          ? (item.count / stats.total_downloads) * 100 
                          : 0;
                        return (
                          <div key={idx} className="space-y-2">
                            <div className="flex justify-between text-xs font-bold uppercase">
                              <span className="text-cyan-50">{item.platform}</span>
                              <span className="text-cyan-100/55">{item.count} items ({percent.toFixed(0)}%)</span>
                            </div>
                            <div className="w-full bg-white/10 rounded-full h-2 overflow-hidden">
                              <div 
                                className="bg-gradient-to-r from-orange-300 to-cyan-300 h-full rounded-full"
                                style={{ width: `${percent}%` }}
                              />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>

              </div>

              {/* REAL-TIME LOG VIEWER */}
              <div className="p-6 glass-panel rounded-2xl space-y-4">
                <h3 className="text-md font-bold text-white border-b border-white/10 pb-2 flex items-center gap-2">
                  <FileText size={18} className="text-cyan-200" />
                  Live Backend Log output (Last 200 rows)
                </h3>

                <div className="bg-slate-950/60 p-4 rounded-xl border border-white/10 h-72 overflow-y-auto font-mono text-[10px] leading-relaxed text-cyan-100/55 whitespace-pre-wrap shadow-inner scrollbar-thin">
                  {logs}
                </div>
              </div>

            </>
          )
        )}

      </div>
    </div>
  );
}
