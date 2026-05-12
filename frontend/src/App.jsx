import { useState, useRef, useEffect } from 'react'
import ChatWindow from './components/ChatWindow'
import VoiceButton from './components/VoiceButton'
import FilesManager from './components/FilesManager'
import Login from './components/Login'
import AvatarVideo from './components/AvatarVideo'
import './App.css'

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [isCheckingAuth, setIsCheckingAuth] = useState(true)
  const [username, setUsername] = useState(null)
  const [messages, setMessages] = useState([])
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [currentCharacter, setCurrentCharacter] = useState('ved-vyasa')
  const [isLoading, setIsLoading] = useState(false)
  const [activeTab, setActiveTab] = useState('chat') // 'chat' or 'files'

  // Check authentication status on mount
  useEffect(() => {
    checkAuth()
  }, [])

  const checkAuth = async () => {
    try {
      const response = await fetch('/api/auth/check', {
        method: 'GET',
        credentials: 'include', // Important for cookies
      })
      const data = await response.json()
      
      if (data.authenticated) {
        setIsAuthenticated(true)
        setUsername(data.username)
      } else {
        setIsAuthenticated(false)
      }
    } catch (error) {
      console.error('Auth check error:', error)
      setIsAuthenticated(false)
    } finally {
      setIsCheckingAuth(false)
    }
  }

  const handleLogin = () => {
    setIsAuthenticated(true)
    checkAuth() // Refresh username
  }

  const handleLogout = async () => {
    try {
      await fetch('/api/logout', {
        method: 'POST',
        credentials: 'include',
      })
      setIsAuthenticated(false)
      setUsername(null)
      setMessages([]) // Clear conversation on logout
    } catch (error) {
      console.error('Logout error:', error)
    }
  }

  const addMessage = (text, sender) => {
    setMessages(prev => [...prev, { text, sender, timestamp: Date.now() }])
  }

const playTTS = async (text) => {
  try {
    setIsSpeaking(true)

    const response = await fetch('/api/tts', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
      body: JSON.stringify({ text }),
    })

    if (response.ok) {
      const audioBlob = await response.blob()
      const audioUrl = URL.createObjectURL(audioBlob)
      const audio = new Audio(audioUrl)

      audio.onended = () => {
        URL.revokeObjectURL(audioUrl)
        setIsSpeaking(false)
      }

      audio.onerror = () => {
        URL.revokeObjectURL(audioUrl)
        setIsSpeaking(false)
      }

      await audio.play()
    } else {
      setIsSpeaking(false)
    }
  } catch (error) {
    console.error('TTS playback error:', error)
    setIsSpeaking(false)
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
        credentials: 'include',
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
        credentials: 'include',
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

  // Show loading state while checking authentication
  if (isCheckingAuth) {
    return (
      <div className="app">
        <div className="app-container">
          <div style={{ textAlign: 'center', padding: '40px' }}>
            <p>Loading...</p>
          </div>
        </div>
      </div>
    )
  }

  // Show login page if not authenticated
  if (!isAuthenticated) {
    return <Login onLogin={handleLogin} />
  }

  // Show main app if authenticated
  return (
    <div className="app">
      <div className="app-container">
        {/* Header with tabs and logout */}
        <div className="app-header">
          <div className="header-left">
            <h1 className="app-title">Hologram Chat</h1>
            <div className="tabs">
              <button 
                className={`tab ${activeTab === 'chat' ? 'active' : ''}`}
                onClick={() => setActiveTab('chat')}
              >
                💬 Chat
              </button>
              <button 
                className={`tab ${activeTab === 'files' ? 'active' : ''}`}
                onClick={() => setActiveTab('files')}
              >
                📁 Files
              </button>
            </div>
          </div>
          <div className="header-right">
            {username && <span className="username-display">Logged in as {username}</span>}
            <button onClick={handleLogout} className="logout-btn">
              Logout
            </button>
          </div>
        </div>

        {/* Tab Content */}
        {activeTab === 'chat' && (
          <div className="chat-tab">
            <AvatarVideo character={currentCharacter} 
isSpeaking={isSpeaking} />
	    <ChatWindow messages={messages} isLoading={isLoading} />
            <VoiceButton onTranscription={handleTranscription} disabled={isLoading} />
          </div>
        )}

        {activeTab === 'files' && (
          <div className="files-tab">
            <FilesManager onUploadSuccess={(data) => {
              addMessage(`Document "${data.message.split(' ')[2]}" uploaded successfully!`, 'system')
            }} />
          </div>
        )}
      </div>
    </div>
  )
}

export default App

