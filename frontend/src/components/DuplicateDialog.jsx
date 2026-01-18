import { useState } from 'react'
import './DuplicateDialog.css'

function DuplicateDialog({ existingFile, onConfirm, onCancel }) {
  const [selectedAction, setSelectedAction] = useState('overwrite')

  const handleConfirm = () => {
    onConfirm(selectedAction)
  }

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  const formatDate = (dateString) => {
    const date = new Date(dateString)
    return date.toLocaleString()
  }

  return (
    <div className="duplicate-dialog-overlay">
      <div className="duplicate-dialog">
        <h2>⚠️ Duplicate File Detected</h2>
        
        <div className="duplicate-info">
          <p>
            A file with identical content already exists:
          </p>
          <div className="existing-file-details">
            <p><strong>Filename:</strong> {existingFile.filename}</p>
            <p><strong>Size:</strong> {formatFileSize(existingFile.file_size)}</p>
            <p><strong>Uploaded:</strong> {formatDate(existingFile.upload_date)}</p>
            <p><strong>Chunks:</strong> {existingFile.chunk_count}</p>
          </div>
        </div>

        <div className="action-selection">
          <p><strong>What would you like to do?</strong></p>
          
          <label className="action-option">
            <input
              type="radio"
              name="action"
              value="overwrite"
              checked={selectedAction === 'overwrite'}
              onChange={(e) => setSelectedAction(e.target.value)}
            />
            <div className="action-label">
              <span className="action-title">Overwrite existing file</span>
              <span className="action-description">
                Replace the existing file with this new version (old chunks will be deleted)
              </span>
            </div>
          </label>

          <label className="action-option">
            <input
              type="radio"
              name="action"
              value="keep_both"
              checked={selectedAction === 'keep_both'}
              onChange={(e) => setSelectedAction(e.target.value)}
            />
            <div className="action-label">
              <span className="action-title">Keep both versions</span>
              <span className="action-description">
                Save this as a new version (filename will be versioned as _v2, _v3, etc.)
              </span>
            </div>
          </label>
        </div>

        <div className="dialog-actions">
          <button onClick={onCancel} className="btn-cancel">
            Cancel
          </button>
          <button onClick={handleConfirm} className="btn-confirm">
            Proceed
          </button>
        </div>
      </div>
    </div>
  )
}

export default DuplicateDialog
