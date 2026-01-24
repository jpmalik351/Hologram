import { useState, useEffect } from 'react'
import FileUpload from './FileUpload'
import './FilesManager.css'

function FilesManager({ onUploadSuccess }) {
  const [files, setFiles] = useState([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [sortBy, setSortBy] = useState('upload_date')
  const [sortOrder, setSortOrder] = useState('desc')
  const [deleteConfirm, setDeleteConfirm] = useState(null) // Store file ID to delete

  // Fetch files when filters change
  useEffect(() => {
    fetchFiles()
  }, [searchTerm, sortBy, sortOrder])

  // Also ensure we fetch on initial mount (in case component mounts before filters are set)
  useEffect(() => {
    console.log('FilesManager: Component mounted, fetching files on initial load')
    fetchFiles()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []) // Empty deps = run only on mount

  const fetchFiles = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams({
        search: searchTerm,
        sort_by: sortBy,
        order: sortOrder
      })

      console.log('FilesManager: Fetching files from /api/files')
      const response = await fetch(`/api/files?${params}`, {
        credentials: 'include'
      })

      console.log('FilesManager: Response status:', response.status)

      if (response.ok) {
        const data = await response.json()
        console.log('FilesManager: Received data:', data)
        console.log('FilesManager: Files count:', data.files?.length || 0)
        setFiles(data.files || [])
      } else {
        const errorData = await response.json().catch(() => ({}))
        console.error('FilesManager: Failed to fetch files:', response.status, errorData)
        if (response.status === 401) {
          console.error('FilesManager: Authentication required')
        }
        setFiles([])
      }
    } catch (error) {
      console.error('FilesManager: Error fetching files:', error)
      setFiles([])
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (fileId) => {
    try {
      const response = await fetch(`/api/files/${fileId}`, {
        method: 'DELETE',
        credentials: 'include'
      })

      if (response.ok) {
        // Refresh file list
        await fetchFiles()
        setDeleteConfirm(null)
      } else {
        const data = await response.json()
        alert(`Failed to delete file: ${data.error}`)
      }
    } catch (error) {
      alert(`Error deleting file: ${error.message}`)
    }
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

  const handleUploadSuccess = (data) => {
    // Refresh file list after successful upload
    fetchFiles()
    if (onUploadSuccess) {
      onUploadSuccess(data)
    }
  }

  return (
    <div className="files-manager">
      <div className="files-header">
        <h2>📁 Knowledge Base Files</h2>
        <p className="files-description">
          Upload and manage documents that will be used for character knowledge
        </p>
      </div>

      {/* Upload Section */}
      <div className="upload-section">
        <FileUpload onUploadSuccess={handleUploadSuccess} />
      </div>

      {/* Search and Filter Section */}
      <div className="files-controls">
        <div className="search-box">
          <input
            type="text"
            placeholder="🔍 Search files..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="search-input"
          />
        </div>
        
        <div className="sort-controls">
          <select 
            value={sortBy} 
            onChange={(e) => setSortBy(e.target.value)}
            className="sort-select"
          >
            <option value="upload_date">Upload Date</option>
            <option value="filename">Filename</option>
            <option value="file_size">File Size</option>
          </select>
          
          <button
            onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
            className="sort-order-btn"
            title={`Sort ${sortOrder === 'asc' ? 'descending' : 'ascending'}`}
          >
            {sortOrder === 'asc' ? '↑' : '↓'}
          </button>
        </div>
      </div>

      {/* Files List */}
      <div className="files-list">
        {loading ? (
          <div className="loading">Loading files...</div>
        ) : files.length === 0 ? (
          <div className="no-files">
            {searchTerm ? (
              <p>No files found matching "{searchTerm}"</p>
            ) : (
              <p>No files uploaded yet. Upload your first document above!</p>
            )}
          </div>
        ) : (
          <div className="files-table-container">
            <table className="files-table">
              <thead>
                <tr>
                  <th>Filename</th>
                  <th>Type</th>
                  <th>Size</th>
                  <th>Chunks</th>
                  <th>Uploaded</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {files.map((file) => (
                  <tr key={file.id}>
                    <td className="filename-cell">
                      <span className="filename" title={file.filename}>
                        {file.filename}
                      </span>
                      {file.filename !== file.original_filename && (
                        <span className="version-badge" title={`Original: ${file.original_filename}`}>
                          versioned
                        </span>
                      )}
                    </td>
                    <td>
                      <span className="file-type-badge">{file.file_type}</span>
                    </td>
                    <td>{formatFileSize(file.file_size)}</td>
                    <td>{file.chunk_count}</td>
                    <td className="date-cell">{formatDate(file.upload_date)}</td>
                    <td>
                      <button
                        onClick={() => setDeleteConfirm(file.id)}
                        className="delete-btn"
                        title="Delete file"
                      >
                        🗑️ Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Delete Confirmation Dialog */}
      {deleteConfirm && (
        <div className="delete-dialog-overlay">
          <div className="delete-dialog">
            <h3>⚠️ Confirm Deletion</h3>
            <p>
              Are you sure you want to delete this file? This will remove all chunks
              from the vector database and cannot be undone.
            </p>
            <div className="dialog-actions">
              <button onClick={() => setDeleteConfirm(null)} className="btn-cancel">
                Cancel
              </button>
              <button onClick={() => handleDelete(deleteConfirm)} className="btn-delete">
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Files Count */}
      {!loading && files.length > 0 && (
        <div className="files-count">
          Showing {files.length} file{files.length !== 1 ? 's' : ''}
        </div>
      )}
    </div>
  )
}

export default FilesManager
