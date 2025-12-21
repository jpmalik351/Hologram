import { useState, useRef, useEffect } from 'react'
import './VoiceButton.css'

function VoiceButton({ onTranscription, disabled }) {
  const [isRecording, setIsRecording] = useState(false)
  const [recordingTime, setRecordingTime] = useState(0)
  const mediaRecorderRef = useRef(null)
  const audioChunksRef = useRef([])
  const streamRef = useRef(null)
  const timerRef = useRef(null)

  useEffect(() => {
    return () => {
      // Cleanup on unmount
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop())
      }
      if (timerRef.current) {
        clearInterval(timerRef.current)
      }
    }
  }, [])

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream

      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus'
      })

      mediaRecorderRef.current = mediaRecorder
      audioChunksRef.current = []

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data)
        }
      }

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' })
        
        // Stop all tracks
        if (streamRef.current) {
          streamRef.current.getTracks().forEach(track => track.stop())
          streamRef.current = null
        }

        // Send to transcription
        if (audioBlob.size > 0) {
          onTranscription(audioBlob)
        }
      }

      mediaRecorder.start()
      setIsRecording(true)
      setRecordingTime(0)

      // Start timer
      timerRef.current = setInterval(() => {
        setRecordingTime(prev => prev + 1)
      }, 1000)

    } catch (error) {
      console.error('Error accessing microphone:', error)
      alert('Could not access microphone. Please check permissions.')
    }
  }

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop()
      setIsRecording(false)
      
      if (timerRef.current) {
        clearInterval(timerRef.current)
        timerRef.current = null
      }
      setRecordingTime(0)
    }
  }

  const handleMouseDown = (e) => {
    e.preventDefault()
    if (!disabled && !isRecording) {
      startRecording()
    }
  }

  const handleMouseUp = (e) => {
    e.preventDefault()
    if (isRecording) {
      stopRecording()
    }
  }

  const handleMouseLeave = (e) => {
    if (isRecording) {
      stopRecording()
    }
  }

  const handleTouchStart = (e) => {
    e.preventDefault()
    if (!disabled && !isRecording) {
      startRecording()
    }
  }

  const handleTouchEnd = (e) => {
    e.preventDefault()
    if (isRecording) {
      stopRecording()
    }
  }

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  return (
    <div className="voice-button-container">
      <button
        className={`voice-button ${isRecording ? 'recording' : ''} ${disabled ? 'disabled' : ''}`}
        onMouseDown={handleMouseDown}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseLeave}
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
        disabled={disabled}
        aria-label={isRecording ? 'Recording... Release to stop' : 'Hold to record'}
      >
        <svg
          width="32"
          height="32"
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          {isRecording ? (
            <rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" />
          ) : (
            <path
              d="M12 1C10.34 1 9 2.34 9 4V12C9 13.66 10.34 15 12 15C13.66 15 15 13.66 15 12V4C15 2.34 13.66 1 12 1ZM19 10V12C19 15.87 15.87 19 12 19C8.13 19 5 15.87 5 12V10H7V12C7 14.76 9.24 17 12 17C14.76 17 17 14.76 17 12V10H19ZM11 22H13V24H11V22Z"
              fill="currentColor"
            />
          )}
        </svg>
      </button>
      {isRecording && (
        <div className="recording-indicator">
          <span className="pulse"></span>
          <span className="recording-text">Recording... {formatTime(recordingTime)}</span>
        </div>
      )}
      {!isRecording && !disabled && (
        <p className="voice-hint">Hold to talk</p>
      )}
    </div>
  )
}

export default VoiceButton

