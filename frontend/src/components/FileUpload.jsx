import { useState } from 'react'
import './FileUpload.css'

function FileUpload({ onUploadSuccess }) {
  const [isUploading, setIsUploading] = useState(false)
  const [uploadStatus, setUploadStatus] = useState(null)

  const handleFileChange = async (event) => {
    const file = event.target.files[0]
    if (!file) return

    // Check file type
    const fileExt = file.name.split('.').pop().toLowerCase()
    if (!['pdf', 'txt', 'text'].includes(fileExt)) {
      setUploadStatus({ type: 'error', message: 'Please upload a PDF or TXT file' })
      return
    }

    setIsUploading(true)
    setUploadStatus(null)

    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      })

      const data = await response.json()

      if (response.ok) {
        setUploadStatus({
          type: 'success',
          message: `${data.message} (${data.chunks_stored} chunks stored)`
        })
        if (onUploadSuccess) {
          onUploadSuccess(data)
        }
      } else {
        setUploadStatus({
          type: 'error',
          message: data.error || 'Upload failed'
        })
      }
    } catch (error) {
      setUploadStatus({
        type: 'error',
        message: `Upload error: ${error.message}`
      })
    } finally {
      setIsUploading(false)
      // Reset file input
      event.target.value = ''
    }
  }

  return (
    <div className="file-upload-container">
      <label htmlFor="file-upload" className="file-upload-label">
        <input
          id="file-upload"
          type="file"
          accept=".pdf,.txt,.text"
          onChange={handleFileChange}
          disabled={isUploading}
          className="file-upload-input"
        />
        <span className="file-upload-button">
          {isUploading ? 'Uploading...' : '📄 Upload Document (PDF/TXT)'}
        </span>
      </label>
      {uploadStatus && (
        <div className={`upload-status ${uploadStatus.type}`}>
          {uploadStatus.message}
        </div>
      )}
    </div>
  )
}

export default FileUpload

