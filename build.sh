#!/bin/bash
set -e

# Measure runtime
SECONDS=0

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

# Verify spec file exists (find the latest generated one)
SPEC_FILE=$(find "$RPMBUILD_DIR/SPECS" -name "eclipse-*.spec" | head -n 1)
if [ -z "$SPEC_FILE" ]; then
    echo "Error: No Spec file found in $RPMBUILD_DIR/SPECS"
    exit 1
fi

# Build RPM
echo "Building RPM..."
# We define _topdir to point to our local rpmbuild directory
rpmbuild --define "_topdir $RPMBUILD_DIR" -bb "$SPEC_FILE"

# Calculate SHA512 of the generated RPM
echo "Calculating checksums..."
find "$RPMBUILD_DIR/RPMS" -name "*.rpm" | while read rpm_file; do
    sha512sum "$rpm_file" > "$rpm_file.sha512"
    echo "Generated checksum for $(basename "$rpm_file")"
    cat "$rpm_file.sha512"
done

# Runtime output
ELAPSED=$SECONDS
HOURS=$((ELAPSED / 3600))
MINUTES=$(((ELAPSED % 3600) / 60))
SECONDS_REST=$((ELAPSED % 60))

echo "Build complete. RPMs should be in $RPMBUILD_DIR/RPMS/"
echo "Total runtime: ${HOURS}h ${MINUTES}m ${SECONDS_REST}s"
