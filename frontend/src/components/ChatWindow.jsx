import { useEffect, useRef, useState } from 'react'
import './ChatWindow.css'

function ChatWindow({ messages, isLoading }) {
  const messagesEndRef = useRef(null)
  const [playingIndex, setPlayingIndex] = useState(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, isLoading])

  const playTTS = async (text, index) => {
    if (playingIndex === index) return // Already playing
    
    setPlayingIndex(index)
    try {
      const response = await fetch('/api/tts', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ text, voice: 'onyx' }),
      })

      if (response.ok) {
        const audioBlob = await response.blob()
        const audioUrl = URL.createObjectURL(audioBlob)
        const audio = new Audio(audioUrl)
        await audio.play()
        audio.onended = () => {
          URL.revokeObjectURL(audioUrl)
          setPlayingIndex(null)
        }
        audio.onerror = () => {
          setPlayingIndex(null)
        }
      } else {
        setPlayingIndex(null)
      }
    } catch (error) {
      console.error('TTS playback error:', error)
      setPlayingIndex(null)
    }
  }

  return (
    <div className="chat-window">
      <div className="messages-container">
        {messages.length === 0 && (
          <div className="empty-state">
            <p>Start a conversation by holding the microphone button and speaking!</p>
          </div>
        )}
        {messages.map((message, index) => (
          <div
            key={index}
            className={`message ${message.sender === 'user' ? 'user-message' : 'assistant-message'}`}
          >
            <div className="message-content">
              {message.text}
            </div>
            {message.sender === 'assistant' && (
              <button
                className="tts-button"
                onClick={() => playTTS(message.text, index)}
                disabled={playingIndex === index}
                aria-label="Play audio"
              >
                {playingIndex === index ? (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <rect x="6" y="4" width="4" height="16" />
                    <rect x="14" y="4" width="4" height="16" />
                  </svg>
                ) : (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M8 5v14l11-7z" />
                  </svg>
                )}
              </button>
            )}
          </div>
        ))}
        {isLoading && (
          <div className="message assistant-message">
            <div className="message-content loading">
              <span className="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
    </div>
  )
}

export default ChatWindow

