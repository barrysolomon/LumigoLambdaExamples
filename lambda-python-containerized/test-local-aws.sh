#!/bin/bash

# Local testing script with AWS services
echo "🧪 Local AWS Testing"
echo "===================="

# Check if virtual environment exists
if [ ! -d ".venv-local" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv-local
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv-local/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Test with AWS services
echo "🚀 Testing with AWS services..."
python lambda_function.py

# Deactivate virtual environment
deactivate

echo ""
echo "✅ Local AWS testing completed!" 