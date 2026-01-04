#!/bin/bash
set -e

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Run the python script to prepare everything
echo "Running fetch_and_prep.py..."
python3 fetch_and_prep.py

# Define RPM build root
RPMBUILD_DIR=$(pwd)/rpmbuild

# Verify spec file exists
SPEC_FILE="$RPMBUILD_DIR/SPECS/eclipse-cpp.spec"
if [ ! -f "$SPEC_FILE" ]; then
    echo "Error: Spec file not found at $SPEC_FILE"
    exit 1
fi

# Build RPM
echo "Building RPM..."
# We define _topdir to point to our local rpmbuild directory
rpmbuild --define "_topdir $RPMBUILD_DIR" -bb "$SPEC_FILE"

echo "Build complete. RPMs should be in $RPMBUILD_DIR/RPMS/"
