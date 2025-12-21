import { useState, useRef, useEffect } from 'react'
import ChatWindow from './components/ChatWindow'
import VoiceButton from './components/VoiceButton'
import './App.css'

function App() {
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)

  const addMessage = (text, sender) => {
    setMessages(prev => [...prev, { text, sender, timestamp: Date.now() }])
  }

  const sendMessage = async (messageText) => {
    if (!messageText.trim()) return

    addMessage(messageText, 'user')
    setIsLoading(true)

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message: messageText }),
      })

      const data = await response.json()
      
      if (response.ok) {
        addMessage(data.response, 'assistant')
      } else {
        addMessage(`Error: ${data.error || 'Failed to get response'}`, 'assistant')
      }
    } catch (error) {
      addMessage(`Error: ${error.message}`, 'assistant')
    } finally {
      setIsLoading(false)
    }
  }

  const handleTranscription = async (audioBlob) => {
    setIsLoading(true)
    
    try {
      // Send audio to transcription endpoint
      const formData = new FormData()
      formData.append('audio', audioBlob, 'recording.webm')

      const transcribeResponse = await fetch('/api/transcribe', {
        method: 'POST',
        body: formData,
      })

      const transcribeData = await transcribeResponse.json()

      if (transcribeResponse.ok && transcribeData.text) {
        // Send transcribed text to chat
        await sendMessage(transcribeData.text)
      } else {
        addMessage(`Transcription error: ${transcribeData.error || 'Failed to transcribe'}`, 'assistant')
      }
    } catch (error) {
      addMessage(`Error: ${error.message}`, 'assistant')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="app">
      <div className="app-container">
        <h1 className="app-title">Hologram Chat</h1>
        <ChatWindow messages={messages} isLoading={isLoading} />
        <VoiceButton onTranscription={handleTranscription} disabled={isLoading} />
      </div>
    </div>
  )
}

export default App

