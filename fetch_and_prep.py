import os
import re
import sys
import tarfile
import requests
from tqdm import tqdm
from pathlib import Path
from urllib.parse import unquote
import datetime

# Configuration
RPMBUILD_DIR = Path("rpmbuild")
DIRS = ["BUILD", "RPMS", "SOURCES", "SPECS", "SRPMS"]

def setup_directories():
    if not RPMBUILD_DIR.exists():
        RPMBUILD_DIR.mkdir()
    for d in DIRS:
        (RPMBUILD_DIR / d).mkdir(exist_ok=True)
    print(f"Created rpmbuild structure in {RPMBUILD_DIR.absolute()}")

def get_download_url():
    print("Please enter the download URL for the Eclipse tarball:")
    print("Example: https://eclipse.mirror.liteserver.nl/technology/epp/downloads/release/2025-12/R/eclipse-cpp-2025-12-R-linux-gtk-x86_64.tar.gz")
    if len(sys.argv) > 1:
        return sys.argv[1]
    
    try:
        url = input("URL: ").strip()
        return url
    except EOFError:
        return None

def parse_filename(filename):
    # Try to match standard eclipse naming convention
    # eclipse-<flavor>-<version>-R-linux-gtk-x86_64.tar.gz
    match = re.match(r'eclipse-([a-z]+)-(\d{4}-\d{2})(-R)?-linux-gtk-x86_64\.tar\.gz', filename)
    if match:
        return match.group(1), match.group(2) # flavor, version
    
    # Fallback/Loose match
    parts = filename.split('-')
    if len(parts) >= 3 and parts[0] == 'eclipse':
        flavor = parts[1]
        # version is usually next, looks like YYYY-MM
        version_match = re.search(r'\d{4}-\d{2}', filename)
        version = version_match.group(0) if version_match else "unknown"
        return flavor, version
        
    return "eclipse", "unknown"

def download_file(url, dest_path):
    print(f"Downloading {url} to {dest_path}")
    response = requests.get(url, stream=True)
    total_size = int(response.headers.get('content-length', 0))
    block_size = 1024
    
    with open(dest_path, 'wb') as f, tqdm(
        desc=dest_path.name,
        total=total_size,
        unit='iB',
        unit_scale=True,
        unit_divisor=1024,
    ) as bar:
        for data in response.iter_content(block_size):
            size = f.write(data)
            bar.update(size)

def extract_icon(tarball_path, dest_dir):
    print("Searching for icon in tarball...")
    icon_name = None
    try:
        with tarfile.open(tarball_path, "r:gz") as tar:
            # Eclipse icon is usually at eclipse/icon.xpm or similar
            # We'll look for icon.xpm or the high res icon
            candidates = [m for m in tar.getmembers() if 'icon.xpm' in m.name or 'eclipse48.png' in m.name or 'eclipse256.png' in m.name]
            
            # Prefer higher res png if available
            best_candidate = None
            for c in candidates:
                if 'eclipse256.png' in c.name:
                    best_candidate = c
                    break
            
            if not best_candidate and candidates:
                 # Fallback to xpm or any found
                 best_candidate = sorted(candidates, key=lambda x: len(x.name))[0]

            if best_candidate:
                print(f"Extracting icon from {best_candidate.name}")
                f = tar.extractfile(best_candidate)
                # Determine extension
                ext = ".xpm"
                if best_candidate.name.endswith(".png"):
                    ext = ".png"
                
                icon_name = f"eclipse{ext}"
                dest_icon_path = dest_dir / icon_name
                with open(dest_icon_path, "wb") as out:
                    out.write(f.read())
                print(f"Icon saved to {dest_icon_path}")
    except Exception as e:
        print(f"Error extracting icon: {e}")
        
    return icon_name

def create_spec_file(flavor, version, tarball_name, icon_filename):
    package_name = f"eclipse-{flavor}"
    rpm_version = version.replace("-", ".")
    
    # Capitalize flavor for summary/description
    flavor_display = flavor.upper() if len(flavor) <= 3 else flavor.capitalize()
    
    # Use default icon if none extracted
    if not icon_filename:
        icon_filename = "eclipse.png" 

    spec_content = f"""
%define __jar_repack 0
%define debug_package %{{nil}}
%define __os_install_post %{{nil}}

Name:           {package_name}
Version:        {rpm_version}
Release:        1%{{?dist}}
Summary:        Eclipse IDE for {flavor_display} Developers
License:        EPL-2.0
URL:            https://www.eclipse.org/
Source0:        {tarball_name}
# Source1 is the icon
Source1:        {icon_filename}

BuildRequires:  desktop-file-utils

%description
Eclipse IDE for {flavor_display} Developers.

%prep
%setup -q -c

%build
# Nothing to build, it is a binary release

%install
rm -rf %{{buildroot}}
mkdir -p %{{buildroot}}/opt/{package_name}
cp -r eclipse/* %{{buildroot}}/opt/{package_name}/

# Install Icon
mkdir -p %{{buildroot}}%{{_datadir}}/pixmaps
# Determine icon extension from Source1
ICON_EXT=$(echo %{{SOURCE1}} | awk -F. '{{print $NF}}')
cp %{{SOURCE1}} %{{buildroot}}%{{_datadir}}/pixmaps/{package_name}.$ICON_EXT

# Create Desktop Entry
mkdir -p %{{buildroot}}%{{_datadir}}/applications
cat > %{{buildroot}}%{{_datadir}}/applications/{package_name}.desktop <<EOF
[Desktop Entry]
Name=Eclipse {flavor_display}
Comment=Eclipse IDE for {flavor_display} Developers
Exec=/opt/{package_name}/eclipse
Icon={package_name}
Terminal=false
Type=Application
Categories=Development;IDE;
StartupNotify=true
EOF

%files
/opt/{package_name}
%{{_datadir}}/applications/{package_name}.desktop
%{{_datadir}}/pixmaps/{package_name}.*

%changelog
* {datetime.datetime.now().strftime("%a %b %d %Y")} Assistant <assistant@example.com> - {rpm_version}-1
- Auto-generated RPM for Eclipse {flavor} {version}
"""
    
    spec_path = RPMBUILD_DIR / "SPECS" / f"{package_name}.spec"
    with open(spec_path, "w") as f:
        f.write(spec_content)
    print(f"Created SPEC file at {spec_path}")
    return spec_path

def main():
    setup_directories()
    
    url = get_download_url()
    if not url:
        print("No URL provided. Exiting.")
        sys.exit(1)
        
    filename = url.split('/')[-1]
    filename = unquote(filename)
    dest_path = RPMBUILD_DIR / "SOURCES" / filename
    
    if not dest_path.exists():
        download_file(url, dest_path)
    else:
        print(f"File {dest_path} already exists. Skipping download.")
        
    flavor, version = parse_filename(filename)
    print(f"Detected Flavor: {flavor}, Version: {version}")
    
    icon_name = extract_icon(dest_path, RPMBUILD_DIR / "SOURCES")
    
    create_spec_file(flavor, version, filename, icon_name)
    print(f"Preparation complete for eclipse-{flavor}.")

if __name__ == "__main__":
    main()
