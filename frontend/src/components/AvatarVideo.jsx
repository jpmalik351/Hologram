import './AvatarVideo.css'

function AvatarVideo({ character = 'ved-vyasa', isSpeaking = false }) {
  const videos = {
    'ved-vyasa': '/videos/vedvyasa.mp4',
    default: '/videos/vedvyasa.mp4',
  }

  const videoSrc = videos[character] || videos.default

  return (
    <div className="avatar-video-shell">
      <video
        className={`avatar-video ${isSpeaking ? 'speaking' : ''}`}
        src={videoSrc}
        autoPlay
        loop
        muted
        playsInline
      />
      <div className="avatar-label">
        {isSpeaking ? 'Speaking...' : 'Ready'}
      </div>
    </div>
  )
}

export default AvatarVideo
