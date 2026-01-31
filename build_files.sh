#!/bin/bash

echo "BUILD START"

# Create a virtual environment if needed (Vercel does this automatically usually)
# But we ensure it's clean
# Install dependencies
python3 -m pip install -r requirements.txt

# Create static directory if it doesn't exist
mkdir -p static
mkdir -p staticfiles

# Run migrations
echo "Running Migrations..."
python3 manage.py migrate --noinput

# Collect static files
echo "Collecting Static Files..."
python3 manage.py collectstatic --noinput --clear

echo "BUILD END"
