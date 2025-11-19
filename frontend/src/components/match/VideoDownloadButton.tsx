"use client"

import { useState, useEffect } from "react"
import { Download, Video, Loader2, CheckCircle2 } from "lucide-react"
import { Button } from "@/components/ui/button"

interface VideoDownloadButtonProps {
  matchId: string;
}

export default function VideoDownloadButton({ matchId }: VideoDownloadButtonProps) {
  const [status, setStatus] = useState<'checking' | 'available' | 'not_generated' | 'generating' | 'error'>('checking')
  const [videoUrl, setVideoUrl] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  // Check if video already exists
  useEffect(() => {
    checkVideoStatus()
  }, [matchId])

  const checkVideoStatus = async () => {
    try {
      setStatus('checking')
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001'
      const response = await fetch(`${apiUrl}/api/matches/${matchId}/video`)

      if (response.ok) {
        const data = await response.json()
        if (data.exists && data.video_url) {
          setVideoUrl(data.video_url)
          setStatus('available')
        } else {
          setStatus('not_generated')
        }
      } else {
        setStatus('not_generated')
      }
    } catch (error) {
      console.error('Error checking video status:', error)
      setStatus('not_generated')
    }
  }

  const generateVideo = async () => {
    try {
      setStatus('generating')
      setErrorMessage(null)

      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001'
      const response = await fetch(`${apiUrl}/api/matches/${matchId}/video`, {
        method: 'POST',
      })

      const data = await response.json()

      if (response.ok && data.success) {
        setVideoUrl(data.video_url)
        setStatus('available')
      } else {
        setErrorMessage(data.error || 'Failed to generate video')
        setStatus('error')
      }
    } catch (error) {
      console.error('Error generating video:', error)
      setErrorMessage('Network error. Please try again.')
      setStatus('error')
    }
  }

  const downloadVideo = () => {
    if (videoUrl) {
      window.open(videoUrl, '_blank')
    }
  }

  // Render based on status
  if (status === 'checking') {
    return (
      <Button variant="outline" disabled className="gap-2">
        <Loader2 className="h-4 w-4 animate-spin" />
        Checking...
      </Button>
    )
  }

  if (status === 'generating') {
    return (
      <Button variant="outline" disabled className="gap-2">
        <Loader2 className="h-4 w-4 animate-spin" />
        Generating Video...
      </Button>
    )
  }

  if (status === 'available') {
    return (
      <div className="flex gap-2">
        <Button
          onClick={downloadVideo}
          className="gap-2 bg-green-600 hover:bg-green-700"
        >
          <Download className="h-4 w-4" />
          Download Video
        </Button>
        <div className="flex items-center text-sm text-green-600">
          <CheckCircle2 className="h-4 w-4 mr-1" />
          Ready
        </div>
      </div>
    )
  }

  if (status === 'error') {
    return (
      <div className="flex flex-col gap-2">
        <Button
          onClick={generateVideo}
          variant="outline"
          className="gap-2"
        >
          <Video className="h-4 w-4" />
          Retry Video Generation
        </Button>
        {errorMessage && (
          <p className="text-sm text-red-500">{errorMessage}</p>
        )}
      </div>
    )
  }

  // status === 'not_generated'
  return (
    <Button
      onClick={generateVideo}
      variant="outline"
      className="gap-2"
    >
      <Video className="h-4 w-4" />
      Generate Video
    </Button>
  )
}
