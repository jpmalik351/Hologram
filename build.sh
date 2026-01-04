#!/bin/bash
# Build script for Render deployment
# This script builds both frontend and backend

set -e  # Exit on error

echo "🚀 Starting build process..."

# Check if Node.js is available
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Installing Node.js..."
    # Render should have Node.js, but if not, we'll fail gracefully
    echo "⚠️  Please ensure Node.js is available in your Render environment"
    exit 1
fi

echo "✅ Node.js version: $(node --version)"
echo "✅ npm version: $(npm --version)"

# Build frontend
echo "📦 Building frontend..."
cd frontend
npm install
npm run build
cd ..

# Verify frontend build
if [ ! -d "frontend/dist" ]; then
    echo "❌ Frontend build failed - dist folder not found"
    exit 1
fi

echo "✅ Frontend built successfully"

# Install backend dependencies
echo "📦 Installing backend dependencies..."
cd backend
pip install -r requirements.txt
cd ..

echo "✅ Build complete!"
echo "📁 Frontend build location: frontend/dist"
echo "🐍 Backend ready to serve from: backend/"
