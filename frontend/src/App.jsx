import { useState, useRef, useEffect } from 'react'
import ChatWindow from './components/ChatWindow'
import VoiceButton from './components/VoiceButton'
import FileUpload from './components/FileUpload'
import './App.css'

function App() {
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)

  const addMessage = (text, sender) => {
    setMessages(prev => [...prev, { text, sender, timestamp: Date.now() }])
  }

  const playTTS = async (text) => {
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
        audio.onended = () => URL.revokeObjectURL(audioUrl)
      }
    } catch (error) {
      console.error('TTS playback error:', error)
    }
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
        // Automatically play TTS for assistant response
        await playTTS(data.response)
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
        <FileUpload onUploadSuccess={(data) => {
          addMessage(`Document "${data.message.split(' ')[2]}" uploaded successfully!`, 'system')
        }} />
        <VoiceButton onTranscription={handleTranscription} disabled={isLoading} />
      </div>
    </div>
  )
}

export default App

