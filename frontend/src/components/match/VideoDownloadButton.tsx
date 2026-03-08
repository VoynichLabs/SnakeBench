"use client"

import { useState, useCallback } from "react"
import { Download, Loader2 } from "lucide-react"

interface VideoDownloadButtonProps {
  matchId: string;
}

export default function VideoDownloadButton({ matchId }: VideoDownloadButtonProps) {
  const [isDownloading, setIsDownloading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const handleDownload = useCallback(async () => {
    const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
    const bucket = process.env.NEXT_PUBLIC_SUPABASE_BUCKET || "matches"

    if (!supabaseUrl) {
      setErrorMessage("Missing Supabase configuration")
      return
    }

    // Supabase respects the download query param for Content-Disposition filename
    const storageUrl = `${supabaseUrl}/storage/v1/object/public/${bucket}/${matchId}/replay.mp4?download=${matchId}.mp4`

    try {
      setIsDownloading(true)
      setErrorMessage(null)

      const link = document.createElement("a")
      link.href = storageUrl
      link.download = `${matchId}.mp4`
      link.rel = "noopener"
      document.body.appendChild(link)
      link.click()
      link.remove()
    } catch (error) {
      console.error("Error downloading video:", error)
      setErrorMessage("Could not download the video. Please try again.")
    } finally {
      setIsDownloading(false)
    }
  }, [matchId])

  return (
    <button
      onClick={handleDownload}
      disabled={isDownloading}
      className="flex items-center gap-1.5 text-gray-400 hover:text-gray-600 transition-colors disabled:opacity-50"
    >
      {isDownloading ? (
        <>
          <Loader2 className="h-3 w-3 animate-spin" />
          <span>Downloading...</span>
        </>
      ) : (
        <>
          <Download className="h-3 w-3" />
          <span>Download MP4</span>
        </>
      )}
    </button>
  )
}
