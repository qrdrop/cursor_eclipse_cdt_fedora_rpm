Eclipse RPM Packager for Fedora
===============================

Project Description
-------------------
This project provides a set of automated scripts to generate native RPM packages for the Eclipse IDE (specifically targeting the C/C++ Developers edition, but capable of handling others) on Fedora and RHEL-based systems.

It performs the following automated tasks:
1. Downloads the specified Eclipse tarball from official mirrors.
2. Verifies the integrity of the download using SHA512 checksums.
3. Extracts high-resolution icons from the archive for system integration.
4. Generates a Fedora-compliant RPM SPEC file.
5. Cleans up unnecessary native libraries for other architectures (ARM, PowerPC, etc.) and operating systems (Windows, macOS) to reduce package size and avoid conflicts.
6. bundles the application into `/opt/` and provides a system-wide binary symlink (e.g., `eclipse-cpp`).
7. Creates a `.desktop` entry for integration with the desktop environment's application menu.

Usage
-----
1. Ensure you have the necessary build dependencies installed (rpm-build, python3, etc.).
2. Run the build script:
   
   ./build.sh

3. When prompted, enter the URL of the Eclipse tarball you wish to package. You can find these on the official Eclipse download page.
   
   Example URL: https://eclipse.mirror.liteserver.nl/technology/epp/downloads/release/2025-12/R/eclipse-cpp-2025-12-R-linux-gtk-x86_64.tar.gz

4. Once the build completes, the RPM package will be available in:
   `rpmbuild/RPMS/x86_64/`

5. Install the generated RPM:
   
   sudo dnf install rpmbuild/RPMS/x86_64/eclipse-cpp-*.rpm

Dependencies Note
-----------------
Please be aware that strict automatic dependency generation has been DISABLED for this package. This is done to prevent the build system from detecting the bundled internal libraries (like the JRE's libjvm.so) as system-wide providers or requiring non-existent system libraries. While the package depends on basic system components (libc, etc.), it relies on the bundled JRE and libraries provided within the Eclipse tarball. Ensure your system has a standard desktop environment installed.

Disclaimer and Liability Exclusion
----------------------------------
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. 

IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

The author does not guarantee that the software is free of errors or that it will function as intended. The author is not responsible for any damage to your computer system, data loss, or other issues that may arise from the use of this software or the generated RPM packages. Use at your own risk.
