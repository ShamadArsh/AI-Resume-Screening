#!/bin/bash
# ============================================================
# setup.sh — One-command setup for local development
# ============================================================
# Usage:  bash setup.sh
# ============================================================

set -e

echo "=========================================="
echo "  AI Resume Screening — Local Setup"
echo "=========================================="
echo ""

# 1. Check Python version
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Install it first: https://python.org"
    exit 1
fi
echo "✅ Python: $(python3 --version)"

# 2. Create virtual environment
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# 3. Activate virtual environment
source venv/bin/activate
echo "✅ Virtual environment activated"

# 4. Upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip --quiet

# 5. Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt
echo "✅ Dependencies installed"

# 6. Create .env from template
if [ ! -f ".env" ]; then
    echo "📝 Creating .env from template..."
    cp .env.example .env
    echo "⚠️  IMPORTANT: Edit .env and add your API keys before running!"
fi

# 7. Create uploads directory
mkdir -p uploads

echo ""
echo "=========================================="
echo "  ✅ Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Edit .env with your API keys:"
echo "   - GEMINI_API_KEY      (required — https://aistudio.google.com/apikey)"
echo "   - AIRTABLE_API_KEY    (optional — falls back to mock mode)"
echo "   - AIRTABLE_BASE_ID    (optional)"
echo "   - GOOGLE_CLIENT_ID    (optional — for Gmail/Calendar)"
echo "   - GOOGLE_CLIENT_SECRET"
echo "   - GMAIL_REFRESH_TOKEN"
echo "   - CALENDAR_REFRESH_TOKEN"
echo ""
echo "2. Start the backend:"
echo "   source venv/bin/activate"
echo "   uvicorn backend.api:app --reload --port 8000"
echo ""
echo "3. In a new terminal, start the dashboard:"
echo "   source venv/bin/activate"
echo "   streamlit run frontend/app.py --server.port 8501"
echo ""
echo "4. Open http://localhost:8501 in your browser"
echo ""
echo "Or run with Docker:"
echo "   docker-compose up -d"
echo ""
