import os
import re
import sys
import tarfile
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
from pathlib import Path

# Configuration
BASE_URL = "https://download.eclipse.org/technology/epp/downloads/release/"
RPMBUILD_DIR = Path("rpmbuild")
DIRS = ["BUILD", "RPMS", "SOURCES", "SPECS", "SRPMS"]

def setup_directories():
    if not RPMBUILD_DIR.exists():
        RPMBUILD_DIR.mkdir()
    for d in DIRS:
        (RPMBUILD_DIR / d).mkdir(exist_ok=True)
    print(f"Created rpmbuild structure in {RPMBUILD_DIR.absolute()}")

def find_latest_release_url():
    print(f"Checking {BASE_URL} for releases...")
    try:
        response = requests.get(BASE_URL)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find year-month directories (e.g., 2025-12/)
        links = soup.find_all('a', href=True)
        release_dirs = []
        for link in links:
            href = link['href'].strip('/')
            if re.match(r'\d{4}-\d{2}', href):
                release_dirs.append(href)
        
        if not release_dirs:
            print("No release directories found.")
            return None, None

        # Sort to find latest (lexicographical sort works for YYYY-MM)
        latest_release = sorted(release_dirs)[-1]
        print(f"Latest release directory: {latest_release}")
        
        # Check for R (Release) build
        r_url = f"{BASE_URL}{latest_release}/R/"
        print(f"Checking {r_url}...")
        r_response = requests.get(r_url)
        
        if r_response.status_code != 200:
            print(f"Release R directory not found for {latest_release}")
            return None
            
        r_soup = BeautifulSoup(r_response.text, 'html.parser')
        r_links = r_soup.find_all('a', href=True)
        
        tarball_name = None
        for link in r_links:
            href = link['href']
            # Looking for eclipse-cpp-*-linux-gtk-x86_64.tar.gz
            if 'eclipse-cpp' in href and 'linux-gtk-x86_64.tar.gz' in href:
                tarball_name = href
                break
        
        if tarball_name:
            full_url = f"{r_url}{tarball_name}"
            print(f"Found download URL: {full_url}")
            return full_url, latest_release
            
    except Exception as e:
        print(f"Error finding latest release: {e}")
        
    return None, None

def download_file(url, dest_path):
    response = requests.get(url, stream=True)
    total_size = int(response.headers.get('content-length', 0))
    block_size = 1024
    
    print(f"Downloading {url} to {dest_path}")
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
    icon_name = "eclipse.png" # Destination name
    found = False
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
             best_candidate = sorted(candidates, key=lambda x: len(x.name))[0] # shortest path usually root

        if best_candidate:
            print(f"Extracting icon from {best_candidate.name}")
            f = tar.extractfile(best_candidate)
            dest_icon_path = dest_dir / icon_name
            with open(dest_icon_path, "wb") as out:
                out.write(f.read())
            print(f"Icon saved to {dest_icon_path}")
            return icon_name
        else:
            print("No icon found in tarball.")
            return None

def create_spec_file(version, icon_filename):
    # Version usually looks like 2025-12. Convert to 2025.12 for RPM friendly version
    rpm_version = version.replace("-", ".")
    
    spec_content = f"""
%define __jar_repack 0
%define debug_package %{{nil}}
%define __os_install_post %{{nil}}

Name:           eclipse-cpp
Version:        {rpm_version}
Release:        1%{{?dist}}
Summary:        Eclipse IDE for C/C++ Developers
License:        EPL-2.0
URL:            https://www.eclipse.org/
Source0:        eclipse-cpp-{version}-R-linux-gtk-x86_64.tar.gz
# If we extracted an icon, we can treat it as Source1 or just assume it is inside the build
Source1:        {icon_filename if icon_filename else "eclipse.png"}

BuildRequires:  desktop-file-utils

%description
The essential tools for any C/C++ developer, including a C/C++ IDE, a Git client, XML Editor, Mylyn, Maven integration and WindowBuilder.

%prep
%setup -q -c

%build
# Nothing to build, it is a binary release

%install
rm -rf %{{buildroot}}
mkdir -p %{{buildroot}}/opt/eclipse-cpp
cp -r eclipse/* %{{buildroot}}/opt/eclipse-cpp/

# Install Icon
mkdir -p %{{buildroot}}%{{_datadir}}/pixmaps
cp %{{SOURCE1}} %{{buildroot}}%{{_datadir}}/pixmaps/eclipse-cpp.png

# Create Desktop Entry
mkdir -p %{{buildroot}}%{{_datadir}}/applications
cat > %{{buildroot}}%{{_datadir}}/applications/eclipse-cpp.desktop <<EOF
[Desktop Entry]
Name=Eclipse C++
Comment=Eclipse IDE for C/C++ Developers
Exec=/opt/eclipse-cpp/eclipse
Icon=eclipse-cpp
Terminal=false
Type=Application
Categories=Development;IDE;
StartupNotify=true
EOF

%files
/opt/eclipse-cpp
%{{_datadir}}/applications/eclipse-cpp.desktop
%{{_datadir}}/pixmaps/eclipse-cpp.png

%changelog
* Sun Jan 04 2026 Assistant <assistant@example.com> - {rpm_version}-1
- Auto-generated RPM for Eclipse C++ {version}
"""
    
    spec_path = RPMBUILD_DIR / "SPECS" / "eclipse-cpp.spec"
    with open(spec_path, "w") as f:
        f.write(spec_content)
    print(f"Created SPEC file at {spec_path}")

def main():
    setup_directories()
    
    url, version = find_latest_release_url()
    if not url:
        # Fallback to the user provided one if scrape fails
        print("Could not find latest release dynamically. Using default/fallback.")
        url = "https://eclipse.mirror.liteserver.nl/technology/epp/downloads/release/2025-12/R/eclipse-cpp-2025-12-R-linux-gtk-x86_64.tar.gz"
        version = "2025-12"
    
    filename = url.split('/')[-1]
    dest_path = RPMBUILD_DIR / "SOURCES" / filename
    
    if not dest_path.exists():
        download_file(url, dest_path)
    else:
        print(f"File {dest_path} already exists. Skipping download.")
        
    icon_name = extract_icon(dest_path, RPMBUILD_DIR / "SOURCES")
    
    create_spec_file(version, icon_name)
    print("Preparation complete. Ready to run rpmbuild.")

if __name__ == "__main__":
    main()
