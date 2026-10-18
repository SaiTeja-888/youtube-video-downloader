"use client";

import React, { useState, useEffect } from "react";
import { useForm } from "react-hook-form";
import { motion, AnimatePresence } from "framer-motion";
import axios from "axios";
import { 
  Clipboard, 
  Trash2, 
  Heart, 
  Download, 
  History, 
  Video, 
  Music, 
  ImageIcon,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  QrCode,
  X
} from "lucide-react";
import { QRCodeSVG } from "qrcode.react";

// Force download helper — creates a temporary hidden <a> with download attribute
// so the browser saves the file instead of navigating to it and playing it.
const forceDownload = (url: string, filename?: string) => {
  const a = document.createElement("a");
  a.href = url;
  a.download = filename || "";
  a.style.display = "none";
  document.body.appendChild(a);
  a.click();
  // Small delay before cleanup so the browser registers the click
  setTimeout(() => document.body.removeChild(a), 200);
};

const playGlassSound = () => {
  try {
    const AudioContextClass =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AudioContextClass) return;
    const audioContext = new AudioContextClass();
    const now = audioContext.currentTime;
    const gain = audioContext.createGain();
    const highTone = audioContext.createOscillator();
    const lowTone = audioContext.createOscillator();

    highTone.type = "sine";
    lowTone.type = "triangle";
    highTone.frequency.setValueAtTime(940, now);
    highTone.frequency.exponentialRampToValueAtTime(1480, now + 0.08);
    lowTone.frequency.setValueAtTime(420, now);
    lowTone.frequency.exponentialRampToValueAtTime(610, now + 0.06);

    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(0.06, now + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.18);

    highTone.connect(gain);
    lowTone.connect(gain);
    gain.connect(audioContext.destination);

    highTone.start(now);
    lowTone.start(now + 0.015);
    highTone.stop(now + 0.18);
    lowTone.stop(now + 0.14);
    window.setTimeout(() => void audioContext.close(), 240);
  } catch {
    // Audio is optional; browsers can block it without affecting the UI.
  }
};

// Get API base path with automatic normalization
const getApiBase = () => {
  if (process.env.NEXT_PUBLIC_API_URL) {
    const trimmed = process.env.NEXT_PUBLIC_API_URL.trim().replace(/\/+$/, "");
    return trimmed.endsWith("/api") ? trimmed : `${trimmed}/api`;
  }
  if (typeof window !== "undefined") {
    // If accessed via default HTTP/HTTPS (port 80/443 e.g. NGINX) or remote host
    if (!window.location.port || window.location.port === "80" || window.location.port === "443" || window.location.hostname !== "localhost") {
      return "/api";
    }
    // If running standalone dev server on port 3000
    if (window.location.port === "3000") {
      return `http://${window.location.hostname}:8000/api`;
    }
  }
  return "http://localhost:8000/api";
};
const API_BASE = getApiBase();

interface MediaFormat {
  format_id: string;
  resolution: string;
  fps: number | null;
  codec: string | null;
  filesize: number | null;
  bitrate: number | null;
  container: string;
  media_type: string;
  url: string | null;
}

interface MediaMetadata {
  url: string;
  title: string;
  duration: number | null;
  thumbnail: string | null;
  uploader: string | null;
  views: number | null;
  upload_date: string | null;
  description: string | null;
  platform: string;
  formats: MediaFormat[];
}

interface DownloadHistoryItem {
  id: string;
  title: string;
  platform: string;
  url: string;
  thumbnail: string | null;
  timestamp: string;
  status: string;
  file_url?: string;
}

export default function Home() {
  // App states
  const [analyzing, setAnalyzing] = useState(false);
  const [metadata, setMetadata] = useState<MediaMetadata | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [descriptionExpanded, setDescriptionExpanded] = useState(false);
  
  // Platforms auto-detect state
  const [detectedPlatform, setDetectedPlatform] = useState<string>("generic");
  
  // Job states
  const [activeJob, setActiveJob] = useState<{
    id: string;
    progress: number;
    status: string;
    error: string | null;
    fileUrl?: string;
  } | null>(null);
  const [displayProgress, setDisplayProgress] = useState(0);

  // Local lists
  const [history, setHistory] = useState<DownloadHistoryItem[]>([]);
  const [favorites, setFavorites] = useState<{ url: string; title: string; platform: string }[]>([]);
  
  // Modal states
  const [qrCodeUrl, setQrCodeUrl] = useState<string | null>(null);

  const { register, handleSubmit, setValue, watch } = useForm({
    defaultValues: { url: "" }
  });

  const urlInput = watch("url");

  // Load history/favorites on start
  useEffect(() => {
    try {
      const storedHistory = localStorage.getItem("downloader_history");
      if (storedHistory) setHistory(JSON.parse(storedHistory));
      
      const storedFavs = localStorage.getItem("downloader_favorites");
      if (storedFavs) setFavorites(JSON.parse(storedFavs));
    } catch (e) {
      console.error("Failed to read localStorage data", e);
    }
  }, []);

  // Sync list helpers
  const saveHistory = (newHistory: DownloadHistoryItem[]) => {
    setHistory(newHistory);
    localStorage.setItem("downloader_history", JSON.stringify(newHistory));
  };

  const saveFavorites = (newFavs: { url: string; title: string; platform: string }[]) => {
    setFavorites(newFavs);
    localStorage.setItem("downloader_favorites", JSON.stringify(newFavs));
  };

  // URL platform auto-detection
  useEffect(() => {
    if (!urlInput) {
      setDetectedPlatform("generic");
      return;
    }
    const val = urlInput.toLowerCase();
    if (val.includes("youtube.com") || val.includes("youtu.be")) {
      setDetectedPlatform("youtube");
    } else if (val.includes("instagram.com") || val.includes("instagr.am")) {
      setDetectedPlatform("instagram");
    } else if (val.includes("twitter.com") || val.includes("x.com")) {
      setDetectedPlatform("twitter");
    } else {
      setDetectedPlatform("generic");
    }
  }, [urlInput]);

  // Paste action
  const handlePaste = async () => {
    playGlassSound();
    try {
      const text = await navigator.clipboard.readText();
      setValue("url", text);
    } catch {
      setErrorMsg("Failed to read clipboard. Please paste manually.");
    }
  };

  // Drag and Drop files / URL
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const data = e.dataTransfer.getData("text");
    if (data) {
      setValue("url", data);
    }
  };

  // Analyze API Call
  const onSubmit = async (data: { url: string }) => {
    playGlassSound();
    const url = data.url.trim();
    setAnalyzing(true);
    setErrorMsg(null);
    setMetadata(null);
    try {
      const response = await axios.post(`${API_BASE}/analyze`, { url });
      setMetadata(response.data);
    } catch (err: unknown) {
      let msg = "Could not analyze the link. Make sure the URL is valid and supported.";
      if (axios.isAxiosError(err)) {
        if (err.response?.status === 404) {
          msg = "API endpoint not found (404). Please ensure the backend is running and NEXT_PUBLIC_API_URL is configured correctly.";
        } else if (err.response?.data?.detail) {
          msg = err.response.data.detail;
        } else if (err.message) {
          msg = err.message;
        }
      } else if (err instanceof Error) {
        msg = err.message;
      }
      setErrorMsg(msg);
    } finally {
      setAnalyzing(false);
    }
  };

  // Trigger download job
  const handleDownload = async (formatId: string) => {
    if (!metadata) return;
    playGlassSound();
    setErrorMsg(null);
    setActiveJob({ id: "pending", progress: 0, status: "pending", error: null });
    setDisplayProgress(0);

    try {
      const res = await axios.post(`${API_BASE}/download`, {
        url: metadata.url,
        format_id: formatId
      });
      
      const jobId = res.data.job_id;
      setActiveJob({ id: jobId, progress: 0, status: "pending", error: null });
      const newHistoryItem: DownloadHistoryItem = {
        id: jobId,
        title: metadata.title,
        platform: metadata.platform,
        url: metadata.url,
        thumbnail: metadata.thumbnail,
        timestamp: new Date().toLocaleTimeString() + " " + new Date().toLocaleDateString(),
        status: "downloading"
      };
      saveHistory([newHistoryItem, ...history]);

      // Start polling
      pollJobStatus(jobId);
    } catch (err: unknown) {
      let msg = "Failed to trigger download job.";
      if (axios.isAxiosError(err)) {
        if (err.response?.status === 404) {
          msg = "API endpoint not found (404). Please ensure the backend is running and NEXT_PUBLIC_API_URL is configured correctly.";
        } else if (err.response?.data?.detail) {
          msg = err.response.data.detail;
        } else if (err.message) {
          msg = err.message;
        }
      } else if (err instanceof Error) {
        msg = err.message;
      }
      setErrorMsg(msg);
      setActiveJob(null);
    }
  };

  // Job Polling
  const pollJobStatus = (jobId: string) => {
    let currentSimulatedProgress = 0;
    const simInterval = setInterval(() => {
      currentSimulatedProgress += 2.2; // reaches 99% in about 4.5 seconds
      if (currentSimulatedProgress > 95) {
        currentSimulatedProgress = 95;
      }
      setDisplayProgress(prev => Math.max(prev, currentSimulatedProgress));
    }, 100);

    const interval = setInterval(async () => {
      try {
        const response = await axios.get(`${API_BASE}/status/${jobId}`);
        const data = response.data;
        
        // If real progress is ahead of simulated, catch up
        if (data.progress > currentSimulatedProgress) {
          currentSimulatedProgress = data.progress;
          setDisplayProgress(data.progress);
        }

        setActiveJob({
          id: jobId,
          progress: data.progress,
          status: data.status,
          error: data.error,
          fileUrl: data.file_url
        });

        // Update history status
        setHistory(prev => {
          const updated = prev.map(item => {
            if (item.id === jobId) {
              return {
                ...item,
                status: data.status,
                file_url: data.file_url ? `${API_BASE.replace("/api", "")}${data.file_url}` : undefined
              };
            }
            return item;
          });
          localStorage.setItem("downloader_history", JSON.stringify(updated));
          return updated;
        });

        if (data.status === "completed" || data.status === "failed") {
          clearInterval(interval);
          clearInterval(simInterval);
          if (data.status === "completed") {
            setDisplayProgress(100);
            if (data.file_url) {
              const fullUrl = `${API_BASE.replace("/api", "")}${data.file_url}`;
              setTimeout(() => {
                forceDownload(fullUrl);
              }, 200);
            }
          } else {
            setDisplayProgress(0);
          }
        }
      } catch (err) {
        console.error("Error polling status:", err);
        clearInterval(interval);
        clearInterval(simInterval);
      }
    }, 500);
  };

  // Add Favorite
  const handleAddFavorite = () => {
    if (!metadata) return;
    playGlassSound();
    const exists = favorites.some(f => f.url === metadata.url);
    if (exists) {
      // Remove
      const filtered = favorites.filter(f => f.url !== metadata.url);
      saveFavorites(filtered);
    } else {
      // Add
      const newFavs = [...favorites, { url: metadata.url, title: metadata.title, platform: metadata.platform }];
      saveFavorites(newFavs);
    }
  };

  // Delete History Item
  const handleDeleteHistoryItem = (id: string) => {
    playGlassSound();
    const filtered = history.filter(h => h.id !== id);
    saveHistory(filtered);
  };

  // Format bytes helper
  const formatBytes = (bytes: number | null) => {
    if (!bytes) return "Unknown";
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return parseFloat((bytes / Math.pow(1024, i)).toFixed(2)) + " " + sizes[i];
  };

  // Format seconds helper
  const formatDuration = (seconds: number | null) => {
    if (!seconds) return "N/A";
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    return hrs > 0 
      ? `${hrs}:${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}` 
      : `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  return (
    <div className="min-h-screen flex flex-col font-sans">
      {/* Animated Ambient Background Circles */}
      <div className="bg-mesh-animation">
        <div className="bg-mesh-circle-1" />
        <div className="bg-mesh-circle-2" />
      </div>

      {/* Navigation Header */}
      <header className="w-full glass-panel border-b sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <div className="w-9 h-9 rounded-xl glass-button flex items-center justify-center text-slate-950 font-black">
              P
            </div>
            <span className="font-extrabold text-xl tracking-tight bg-gradient-to-r from-orange-300 via-cyan-200 to-cyan-400 bg-clip-text text-transparent">
              POSTLINK
              <span className="ml-2 text-sm font-bold uppercase tracking-wider text-cyan-100/70">media downloader</span>
            </span>
          </div>

          <div className="flex items-center space-x-4">
            <a 
              href="/admin" 
              onClick={playGlassSound}
              className="text-sm font-semibold px-4 py-2 rounded-full glass-chip hover:border-cyan-300/50 hover:bg-cyan-300/10 transition-all text-cyan-100 hover:text-white"
            >
              Admin Dashboard
            </a>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-12 flex flex-col items-center">
        
        {/* HERO SECTION */}
        <section className="text-center max-w-2xl mt-4 mb-10">
          <h1 className="text-5xl font-extrabold tracking-tight mb-4 text-white leading-tight">
            POSTLINK <br />
            <span className="bg-gradient-to-r from-orange-300 via-cyan-100 to-cyan-400 bg-clip-text text-transparent">
              media downloader
            </span>
          </h1>
          <p className="text-cyan-100/70 text-lg">
            Download reels, images, videos, and direct media links through a crisp glass interface.
          </p>
        </section>

        {/* INPUT FORM PANEL */}
        <section 
          onDragOver={handleDragOver}
          onDrop={handleDrop}
          className="w-full max-w-3xl glass-panel rounded-3xl p-8 glow-card transition-all mb-8 border"
        >
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
            <div className="relative flex flex-col md:flex-row items-stretch gap-3">
              <div className="relative flex-1">
                <input
                  type="text"
                  placeholder="Paste a YouTube, Instagram, X/Twitter, or direct media URL..."
                  className="w-full h-14 pl-5 pr-12 rounded-2xl glass-input outline-none text-cyan-50 placeholder-cyan-100/40 transition-all font-medium text-sm"
                  {...register("url", { required: true })}
                />
                
                <button
                  type="button"
                  onClick={handlePaste}
                  title="Paste clipboard"
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-cyan-100/60 hover:text-orange-200 transition-colors p-1.5 hover:bg-white/10 rounded-lg"
                >
                  <Clipboard size={18} />
                </button>
              </div>

              <button
                type="submit"
                disabled={analyzing}
                className="h-14 px-8 rounded-2xl glass-button disabled:opacity-50 disabled:cursor-not-allowed font-black text-slate-950 active:scale-95 transition-all flex items-center justify-center gap-2 cursor-pointer"
              >
                {analyzing ? (
                  <>
                    <RefreshCw className="animate-spin" size={18} />
                    Analyzing...
                  </>
                ) : (
                  "Analyze Link"
                )}
              </button>
            </div>
            
            {/* Auto Detected Platform Badges */}
            <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
              <span className="text-xs font-semibold text-cyan-100/50 mr-2 uppercase tracking-wider">Supported Platforms:</span>
              <span className={`px-3 py-1.5 rounded-full text-xs font-bold transition-all border ${detectedPlatform === 'youtube' ? 'bg-orange-400/15 border-orange-300 text-orange-200 shadow-sm shadow-orange-400/10' : 'glass-chip text-cyan-100/45'}`}>
                YouTube
              </span>
              <span className={`px-3 py-1.5 rounded-full text-xs font-bold transition-all border ${detectedPlatform === 'instagram' ? 'bg-cyan-300/15 border-cyan-300 text-cyan-100 shadow-sm shadow-cyan-300/10' : 'glass-chip text-cyan-100/45'}`}>
                Instagram
              </span>
              <span className={`px-3 py-1.5 rounded-full text-xs font-bold transition-all border ${detectedPlatform === 'twitter' ? 'bg-cyan-300/15 border-cyan-300 text-cyan-100 shadow-sm shadow-cyan-300/10' : 'glass-chip text-cyan-100/45'}`}>
                Twitter / X
              </span>
            </div>
          </form>

          {/* Drag & drop helper text */}
          <div className="text-center mt-3">
            <span className="text-xs text-cyan-100/45 font-medium">Or drag and drop the media link anywhere on the box</span>
          </div>
        </section>

        {/* ERROR DISPLAY */}
        {errorMsg && (
          <motion.div 
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="w-full max-w-3xl p-4 bg-orange-500/10 border border-orange-300/30 rounded-2xl text-orange-100 text-sm flex items-start gap-3 mb-8 backdrop-blur-xl"
          >
            <AlertTriangle className="shrink-0 mt-0.5" size={18} />
            <div>
              <h4 className="font-bold">Extraction Error</h4>
              <p className="mt-0.5 font-medium">{errorMsg}</p>
            </div>
          </motion.div>
        )}

        {/* ACTIVE DOWNLOAD / PROGRESS NOTIFICATION */}
        {activeJob && (
          <div className="w-full max-w-3xl p-6 rounded-2xl glass-panel glow-card border mb-8 flex flex-col space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-xl bg-cyan-300/10 text-cyan-200 animate-pulse">
                  <Download size={20} />
                </div>
                <div>
                  <h4 className="font-bold text-sm text-white">
                    {activeJob.status === "pending" && "Initializing download job..."}
                    {activeJob.status === "downloading" && `Downloading — ${displayProgress.toFixed(1)}%`}
                    {activeJob.status === "completed" && "Download ready!"}
                    {activeJob.status === "failed" && "Download failed"}
                  </h4>
                  <p className="text-xs text-cyan-100/55 font-medium">
                    {activeJob.status === "pending" && "Connecting to media server..."}
                    {activeJob.status === "downloading" && (
                      displayProgress < 5
                        ? "Starting download stream..."
                        : displayProgress > 95
                          ? "Finalizing & merging media..."
                          : "Downloading media data..."
                    )}
                    {activeJob.status === "completed" && "File saved locally. Auto-transfer initiated."}
                    {activeJob.status === "failed" && (activeJob.error || "Temporary service timeout.")}
                  </p>
                </div>
              </div>
              <span className={`px-2.5 py-1 rounded-full text-xs font-bold capitalize ${
                activeJob.status === 'completed' ? 'bg-cyan-300/10 text-cyan-100 border border-cyan-300/30' :
                activeJob.status === 'failed' ? 'bg-orange-500/10 text-orange-200 border border-orange-300/30' :
                'bg-orange-400/10 text-orange-200 border border-orange-300/30'
              }`}>
                {activeJob.status}
              </span>
            </div>

            {/* Progress bar */}
            {(activeJob.status === "downloading" || activeJob.status === "pending") && (
              <div className="w-full bg-white/10 rounded-full h-3 overflow-hidden">
                {activeJob.status === "pending" ? (
                  <div className="bg-gradient-to-r from-orange-300 via-cyan-200 to-orange-300 h-full rounded-full animate-progress-indeterminate" />
                ) : (
                  <div 
                    className="bg-gradient-to-r from-orange-300 to-cyan-300 h-full rounded-full transition-all duration-200 ease-out relative overflow-hidden"
                    style={{ width: `${Math.max(displayProgress, 2)}%` }}
                  >
                    <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-shimmer" />
                  </div>
                )}
              </div>
            )}

            {/* Quick action buttons */}
            {activeJob.status === "completed" && activeJob.fileUrl && (
              <div className="flex gap-2 justify-end">
                <button
                  onClick={() => {
                    playGlassSound();
                    forceDownload(`${API_BASE.replace("/api", "")}${activeJob.fileUrl}`);
                  }}
                  className="px-4 py-2 glass-button text-slate-950 font-black rounded-xl text-xs flex items-center gap-1.5 shadow cursor-pointer"
                >
                  <Download size={14} /> Download Again
                </button>
                <button
                  onClick={() => {
                    playGlassSound();
                    setQrCodeUrl(`${API_BASE.replace("/api", "")}${activeJob.fileUrl}`);
                  }}
                  className="px-4 py-2 glass-chip hover:bg-white/10 rounded-xl text-xs font-bold text-cyan-100 flex items-center gap-1.5"
                >
                  <QrCode size={14} /> Mobile QR Code
                </button>
              </div>
            )}
          </div>
        )}

        {/* METADATA RESULTS */}
        <AnimatePresence>
          {metadata && (
            <motion.section 
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 15 }}
              className="w-full max-w-3xl glass-panel rounded-3xl p-8 border mb-12 space-y-8"
            >
              
              {/* Media details info card */}
              <div className="flex flex-col md:flex-row gap-6">
                {/* Thumbnail */}
                <div className="w-full md:w-64 shrink-0 rounded-2xl overflow-hidden aspect-video bg-slate-950/60 relative border border-white/10 shadow">
                  {metadata.thumbnail ? (
                    <img 
                      src={metadata.thumbnail} 
                      alt={metadata.title} 
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-cyan-100/40 font-bold text-sm">
                      No Thumbnail
                    </div>
                  )}
                  {metadata.duration && (
                    <span className="absolute bottom-2 right-2 px-2 py-0.5 bg-black/80 rounded-md text-xs font-bold text-white">
                      {formatDuration(metadata.duration)}
                    </span>
                  )}
                </div>

                {/* Details */}
                <div className="flex-1 flex flex-col justify-between space-y-4">
                  <div>
                    <div className="flex items-start justify-between gap-4">
                      <h2 className="text-xl font-extrabold text-white leading-tight">
                        {metadata.title}
                      </h2>
                      
                      {/* Heart (Favorite Pin) */}
                      <button
                        onClick={handleAddFavorite}
                        className={`p-2 rounded-xl border transition-colors ${
                          favorites.some(f => f.url === metadata.url)
                            ? 'bg-orange-400/10 border-orange-300/50 text-orange-200'
                            : 'border-white/10 text-cyan-100/55 hover:text-orange-200 hover:bg-white/10'
                        }`}
                        title="Add to Favorites"
                      >
                        <Heart size={16} fill={favorites.some(f => f.url === metadata.url) ? "#ffb86b" : "none"} />
                      </button>
                    </div>

                    <div className="flex flex-wrap gap-x-4 gap-y-2 mt-3 text-xs font-semibold text-cyan-100/55">
                      <span>Uploader: <strong className="text-cyan-50">{metadata.uploader}</strong></span>
                      {metadata.views && <span>Views: <strong className="text-cyan-50">{metadata.views.toLocaleString()}</strong></span>}
                      {metadata.upload_date && (
                        <span>
                          Upload Date: <strong className="text-cyan-50">
                            {metadata.upload_date.slice(0, 4)}-{metadata.upload_date.slice(4, 6)}-{metadata.upload_date.slice(6, 8)}
                          </strong>
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Description collapsed toggle */}
                  {metadata.description && (
                    <div className="pt-2">
                      <div className={`text-xs text-cyan-100/60 leading-relaxed font-medium ${descriptionExpanded ? '' : 'line-clamp-2'}`}>
                        {metadata.description}
                      </div>
                      <button
                        onClick={() => setDescriptionExpanded(!descriptionExpanded)}
                        className="text-xs font-bold text-orange-200 hover:text-cyan-100 mt-1 flex items-center gap-0.5"
                      >
                        {descriptionExpanded ? (
                          <>Read Less <ChevronUp size={14} /></>
                        ) : (
                          <>Read More <ChevronDown size={14} /></>
                        )}
                      </button>
                    </div>
                  )}
                </div>
              </div>

              {/* FORMAT TABLES */}
              <div>
                <h3 className="text-md font-bold text-white border-b border-white/10 pb-2 mb-4 flex items-center gap-2">
                  <Video size={18} className="text-cyan-200" />
                  Available Download Formats
                </h3>
                
                <div className="overflow-x-auto rounded-xl border border-white/10">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="bg-white/[0.08] border-b border-white/10 text-cyan-100/55 font-bold uppercase tracking-wider">
                        <th className="p-3.5">Quality / Format</th>
                        <th className="p-3.5">Container</th>
                        <th className="p-3.5">Codec</th>
                        <th className="p-3.5">Est. Size</th>
                        <th className="p-3.5 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-800/50">
                      {metadata.formats.map((f, i) => (
                        <tr key={i} className="hover:bg-white/[0.08] transition-colors font-medium">
                          <td className="p-3.5 flex items-center gap-2">
                            {f.media_type === 'audio' ? (
                              <Music size={14} className="text-orange-200" />
                            ) : f.media_type === 'image' ? (
                              <ImageIcon size={14} className="text-cyan-200" />
                            ) : (
                              <Video size={14} className="text-cyan-200" />
                            )}
                            <span className="font-bold text-white">
                              {f.resolution} {f.fps ? `@ ${f.fps}fps` : ''}
                            </span>
                          </td>
                          <td className="p-3.5 uppercase text-cyan-100/55 font-bold">{f.container}</td>
                          <td className="p-3.5 text-cyan-100/50 font-mono">{f.codec || 'unknown'}</td>
                          <td className="p-3.5 text-cyan-50/80">{formatBytes(f.filesize)}</td>
                          <td className="p-3.5 text-right">
                            <button
                              onClick={() => handleDownload(f.format_id)}
                              disabled={!!(activeJob && (activeJob.status === 'pending' || activeJob.status === 'downloading'))}
                              className="px-3 py-1.5 bg-cyan-300/10 hover:bg-cyan-300 text-cyan-100 hover:text-slate-950 rounded-lg font-bold transition-all border border-cyan-300/20 cursor-pointer text-xs disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:bg-cyan-300/10 disabled:hover:text-cyan-100"
                            >
                              {activeJob && (activeJob.status === 'pending' || activeJob.status === 'downloading') ? 'In Progress...' : 'Download'}
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </motion.section>
          )}
        </AnimatePresence>

        {/* SIDE BAR / SECONDARY CARDS FOR HISTORY & FAVS */}
        <section className="grid grid-cols-1 md:grid-cols-2 gap-8 w-full max-w-3xl">
          
          {/* HISTORY LOG */}
          <div className="glass-panel border rounded-3xl p-6 glow-card">
            <h3 className="text-md font-bold text-white mb-4 flex items-center gap-2 border-b border-white/10 pb-2">
              <History size={18} className="text-cyan-200" />
              Recent Downloads
            </h3>

            {history.length === 0 ? (
              <div className="text-center py-8 text-cyan-100/45 text-xs font-semibold">
                No recent downloads.
              </div>
            ) : (
              <div className="space-y-4 max-h-[300px] overflow-y-auto pr-1">
                {history.map((item) => (
                  <div key={item.id} className="flex gap-3 items-center justify-between border-b border-white/10 pb-3">
                    <div className="flex gap-2 items-center min-w-0">
                      <div className="w-12 h-8 rounded overflow-hidden shrink-0 bg-slate-950/70 border border-white/10">
                        {item.thumbnail ? (
                          <img src={item.thumbnail} alt={item.title} className="w-full h-full object-cover" />
                        ) : (
                          <div className="w-full h-full bg-white/5" />
                        )}
                      </div>
                      <div className="min-w-0">
                        <h4 className="text-xs font-bold text-white truncate" title={item.title}>
                          {item.title}
                        </h4>
                        <span className="text-[10px] text-cyan-100/45 uppercase font-bold tracking-wider">
                          {item.platform} • {item.status}
                        </span>
                      </div>
                    </div>
                    <div className="flex gap-1">
                      {item.status === 'completed' && item.file_url && (
                        <>
                          <button
                            onClick={() => {
                              playGlassSound();
                              forceDownload(item.file_url!);
                            }}
                            className="p-1.5 hover:bg-white/10 rounded-lg text-cyan-200 cursor-pointer"
                            title="Download"
                          >
                            <Download size={14} />
                          </button>
                          <button
                            onClick={() => {
                              playGlassSound();
                              setQrCodeUrl(item.file_url || null);
                            }}
                            className="p-1.5 hover:bg-white/10 rounded-lg text-cyan-100/60"
                            title="QR Code Share"
                          >
                            <QrCode size={14} />
                          </button>
                        </>
                      )}
                      <button
                        onClick={() => handleDeleteHistoryItem(item.id)}
                        className="p-1.5 hover:bg-white/10 rounded-lg text-cyan-100/45 hover:text-orange-200"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* FAVORITE URLS */}
          <div className="glass-panel border rounded-3xl p-6 glow-card">
            <h3 className="text-md font-bold text-white mb-4 flex items-center gap-2 border-b border-white/10 pb-2">
              <Heart size={18} className="text-orange-200" />
              Pinned Favorites
            </h3>

            {favorites.length === 0 ? (
              <div className="text-center py-8 text-cyan-100/45 text-xs font-semibold">
                No pinned bookmarks. Click heart on results.
              </div>
            ) : (
              <div className="space-y-4 max-h-[300px] overflow-y-auto pr-1">
                {favorites.map((item, idx) => (
                  <div key={idx} className="flex gap-2 items-center justify-between border-b border-white/10 pb-3">
                    <div className="min-w-0 flex-1">
                      <h4 className="text-xs font-bold text-white truncate">
                        {item.title}
                      </h4>
                      <span className="text-[10px] text-cyan-100/45 capitalize">{item.platform}</span>
                    </div>
                    <div className="flex gap-1 shrink-0">
                      <button
                        onClick={() => {
                          playGlassSound();
                          setValue("url", item.url);
                        }}
                        className="px-2.5 py-1 bg-cyan-300/10 hover:bg-cyan-300 text-cyan-100 hover:text-slate-950 rounded-lg text-[10px] font-bold"
                      >
                        Load Link
                      </button>
                      <button
                        onClick={() => {
                          playGlassSound();
                          const filtered = favorites.filter(f => f.url !== item.url);
                          saveFavorites(filtered);
                        }}
                        className="p-1 hover:bg-white/10 rounded text-cyan-100/45 hover:text-orange-200"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>

      </main>

      {/* FOOTER */}
      <footer className="w-full py-8 mt-16 glass-panel border-t border-white/10 text-center text-xs text-cyan-100/45 font-semibold">
        <div className="max-w-7xl mx-auto px-6 space-y-2">
          <p>© {new Date().getFullYear()} POSTLINK media downloader. Licensed for personal usage only.</p>
          <div className="flex justify-center space-x-4">
            <a href="#" className="hover:text-orange-200 transition-colors">Privacy Policy</a>
            <span>•</span>
            <a href="#" className="hover:text-cyan-100 transition-colors">Terms of Service</a>
            <span>•</span>
            <a href="#" className="hover:text-orange-200 transition-colors">Supported Sites</a>
          </div>
        </div>
      </footer>

      {/* QR CODE GENERATOR MODAL */}
      <AnimatePresence>
        {qrCodeUrl && (
          <div className="fixed inset-0 bg-black/70 backdrop-blur-xl flex items-center justify-center p-4 z-50">
            <motion.div 
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              className="glass-panel rounded-3xl p-6 max-w-sm w-full text-center space-y-6 relative shadow-2xl"
            >
              <button
                onClick={() => {
                  playGlassSound();
                  setQrCodeUrl(null);
                }}
                className="absolute right-4 top-4 text-cyan-100/55 hover:text-white p-1 rounded-lg hover:bg-white/10 transition-all"
              >
                <X size={18} />
              </button>

              <div>
                <h3 className="font-extrabold text-lg text-white">Mobile Share</h3>
                <p className="text-xs text-cyan-100/50 mt-1">Scan this QR Code with your mobile phone camera to download directly to your device.</p>
              </div>

              <div className="bg-white p-4 rounded-2xl w-48 h-48 mx-auto flex items-center justify-center shadow-inner">
                <QRCodeSVG value={qrCodeUrl} size={168} />
              </div>

              <div className="flex gap-2">
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(qrCodeUrl);
                    alert("Download link copied to clipboard!");
                  }}
                  className="flex-1 py-2.5 glass-chip hover:bg-white/10 text-cyan-100 font-bold rounded-xl text-xs"
                >
                  Copy URL
                </button>
                <button
                  onClick={() => {
                    playGlassSound();
                    setQrCodeUrl(null);
                  }}
                  className="flex-1 py-2.5 glass-button text-slate-950 font-black rounded-xl text-xs"
                >
                  Dismiss
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

    </div>
  );
}
