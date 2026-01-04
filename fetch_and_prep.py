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

import hashlib

def verify_checksum(file_path, sha512_url):
    print(f"Downloading checksum from {sha512_url}...")
    try:
        response = requests.get(sha512_url)
        response.raise_for_status()
        # Checksum file format usually: "SHA512_HASH  FILENAME" or just "SHA512_HASH"
        expected_hash = response.text.split()[0].strip()
        print(f"Expected SHA512: {expected_hash[:16]}...")
        
        print(f"Calculating SHA512 for {file_path.name}...")
        sha512_hash = hashlib.sha512()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha512_hash.update(byte_block)
        
        calculated_hash = sha512_hash.hexdigest()
        print(f"Calculated SHA512: {calculated_hash[:16]}...")
        
        if calculated_hash.lower() == expected_hash.lower():
            print("Checksum verified successfully.")
            return True
        else:
            print("Checksum verification FAILED!")
            return False
            
    except Exception as e:
        print(f"Error checking checksum: {e}")
        return False

def extract_icon(tarball_path, dest_dir):
    print("Searching for icon in tarball...")
    icon_name = None
    try:
        # Try opening as gzip first (common for .tar.gz)
        mode = "r:gz"
        try:
            tar = tarfile.open(tarball_path, mode)
        except tarfile.ReadError:
             # Fallback to r:* if not gz, or just r
             mode = "r"
             tar = tarfile.open(tarball_path, mode)

        with tar:
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
# Disable automatic dependency generation to avoid picking up bundled internal libraries
%define _use_internal_dependency_generator 0
%define __find_requires %{{nil}}
%define __find_provides %{{nil}}
# Alternatively, filtering:
%global __provides_exclude_from ^/opt/{package_name}/.*$
%global __requires_exclude_from ^/opt/{package_name}/.*$

%description
Eclipse IDE for {flavor_display} Developers.

%prep
# Create a specific build directory to avoid collision
mkdir -p %{{name}}-%{{version}}-build
cd %{{name}}-%{{version}}-build
tar -xf %{{SOURCE0}}

%build
cd %{{name}}-%{{version}}-build
# Nothing to build, it is a binary release

%install
cd %{{name}}-%{{version}}-build
rm -rf %{{buildroot}}
mkdir -p %{{buildroot}}/opt/{package_name}
cp -r eclipse/* %{{buildroot}}/opt/{package_name}/

# Cleanup unused plugins and native libs for other architectures
# Remove Arch-specific fragments
rm -rf %{{buildroot}}/opt/{package_name}/plugins/*.aarch64*
rm -rf %{{buildroot}}/opt/{package_name}/plugins/*.arm*
rm -rf %{{buildroot}}/opt/{package_name}/plugins/*.ppc*
rm -rf %{{buildroot}}/opt/{package_name}/plugins/*.riscv*
rm -rf %{{buildroot}}/opt/{package_name}/plugins/*.s390*
rm -rf %{{buildroot}}/opt/{package_name}/plugins/*.sparc*
rm -rf %{{buildroot}}/opt/{package_name}/plugins/*.mips*

# Remove OS-specific fragments not for Linux
rm -rf %{{buildroot}}/opt/{package_name}/plugins/*.macosx*
rm -rf %{{buildroot}}/opt/{package_name}/plugins/*.win32*

# Remove JNA/JFFI native lib directories for other arches/OSes
# Broadly find any directory that looks like a non-linux/non-x86_64 target
find %{{buildroot}}/opt/{package_name}/plugins -type d \\( \\
    -name "*aarch64*" -o \\
    -name "*arm*" -o \\
    -name "*ppc*" -o \\
    -name "*riscv*" -o \\
    -name "*s390*" -o \\
    -name "*sparc*" -o \\
    -name "*mips*" -o \\
    -name "*loongarch*" -o \\
    -name "*freebsd*" -o \\
    -name "*openbsd*" -o \\
    -name "*netbsd*" -o \\
    -name "*dragonfly*" -o \\
    -name "*sunos*" -o \\
    -name "*solaris*" -o \\
    -name "*aix*" -o \\
    -name "*darwin*" -o \\
    -name "*macosx*" -o \\
    -name "*win32*" -o \\
    -name "*windows*" \\
\\) -exec rm -rf {{}} +

# Also explicitly remove any .so / .dll / .dylib files that might be in odd places if they match these patterns
find %{{buildroot}}/opt/{package_name}/plugins -type f \\( \\
    -name "*.dylib" -o \\
    -name "*.dll" \\
\\) -delete

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
Exec={package_name}
Icon={package_name}
Terminal=false
Type=Application
Categories=Development;IDE;
StartupNotify=true
EOF

# Create symlink in /usr/bin
mkdir -p %{{buildroot}}%{{_bindir}}
ln -s /opt/{package_name}/eclipse %{{buildroot}}%{{_bindir}}/{package_name}

%files
/opt/{package_name}
%{{_bindir}}/{package_name}
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

def main():
    setup_directories()
    
    url = get_download_url()
    if not url:
        print("No URL provided. Exiting.")
        sys.exit(1)
        
    filename = url.split('/')[-1]
    filename = unquote(filename)
    dest_path = RPMBUILD_DIR / "SOURCES" / filename
    
    # Download file if not exists or check failed (will be implemented below)
    download_needed = not dest_path.exists()
    
    if download_needed:
        download_file(url, dest_path)
    else:
        print(f"File {dest_path} already exists. Verifying checksum...")
        
    # Verify checksum
    # Construct checksum URL: usually append .sha512
    # Note: Eclipse mirrors sometimes have specific structures, but usually .sha512 works on the file URL
    sha512_url = url + ".sha512"
    if not verify_checksum(dest_path, sha512_url):
        print("Checksum verification failed or could not be performed.")
        # If the file existed but failed checksum, we might want to re-download.
        # But for now, we just warn or exit.
        if not download_needed:
             print("Existing file is corrupt. Re-downloading...")
             download_file(url, dest_path)
             if not verify_checksum(dest_path, sha512_url):
                 print("Checksum failed even after re-download. Aborting.")
                 sys.exit(1)
        else:
             print("Downloaded file is corrupt. Aborting.")
             sys.exit(1)
        
    flavor, version = parse_filename(filename)
    print(f"Detected Flavor: {flavor}, Version: {version}")
    
    icon_name = extract_icon(dest_path, RPMBUILD_DIR / "SOURCES")
    
    create_spec_file(flavor, version, filename, icon_name)
    print(f"Preparation complete for eclipse-{flavor}.")

if __name__ == "__main__":
    main()
