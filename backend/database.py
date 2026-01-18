"""
Database Models and Configuration

Provides SQLAlchemy setup and models for file tracking.
Uses PostgreSQL for persistent storage of uploaded file metadata.
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

# Initialize SQLAlchemy
db = SQLAlchemy()


def init_db(app):
    """
    Initialize database with Flask app.
    
    Args:
        app: Flask application instance
    
    Note:
        - Requires DATABASE_URL environment variable
        - Automatically creates tables if they don't exist
    """
    database_url = os.environ.get('DATABASE_URL')
    
    # Handle Render's postgres:// vs postgresql:// URL format
    if database_url and database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///hologram.db'  # Fallback to SQLite for dev
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,  # Verify connections before using
        'pool_recycle': 300,    # Recycle connections after 5 minutes
    }
    
    db.init_app(app)
    
    with app.app_context():
        db.create_all()


class UploadedFile(db.Model):
    """
    Model for tracking uploaded files.
    
    Stores metadata about files uploaded to the vector database,
    including references to Pinecone chunks for deletion capability.
    """
    __tablename__ = 'uploaded_files'
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False, index=True)  # Current filename (may be versioned)
    original_filename = db.Column(db.String(255), nullable=False)  # Original filename before versioning
    file_hash = db.Column(db.String(64), nullable=False, index=True)  # SHA256 hash for duplicate detection
    file_size = db.Column(db.Integer, nullable=False)  # File size in bytes
    file_type = db.Column(db.String(10), nullable=False)  # File extension (.pdf, .txt)
    upload_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    chunk_ids = db.Column(db.JSON, nullable=False)  # Array of Pinecone chunk IDs
    chunk_count = db.Column(db.Integer, nullable=False)  # Number of chunks
    
    def to_dict(self):
        """
        Convert model to dictionary for JSON serialization.
        
        Returns:
            dict: File metadata
        """
        return {
            'id': self.id,
            'filename': self.filename,
            'original_filename': self.original_filename,
            'file_hash': self.file_hash,
            'file_size': self.file_size,
            'file_type': self.file_type,
            'upload_date': self.upload_date.isoformat() if self.upload_date else None,
            'chunk_ids': self.chunk_ids,
            'chunk_count': self.chunk_count
        }
    
    def __repr__(self):
        return f'<UploadedFile {self.filename}>'
