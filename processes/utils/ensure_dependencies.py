"""
Dependency Checker
----------------
Ensures all required dependencies for the file organizer utility are installed.
"""

import sys
import subprocess
import pkg_resources

def check_dependency(package_name, min_version=None):
    """Check if a package is installed with the required version
    
    Args:
        package_name: The name of the package to check
        min_version: Minimum required version (optional)
        
    Returns:
        bool: True if installed with correct version, False otherwise
    """
    try:
        package = pkg_resources.get_distribution(package_name)
        print(f"Found {package.project_name} {package.version}")
        
        if min_version and pkg_resources.parse_version(package.version) < pkg_resources.parse_version(min_version):
            print(f"Warning: {package_name} version {package.version} is less than required {min_version}")
            return False
        return True
    except pkg_resources.DistributionNotFound:
        print(f"Not found: {package_name}")
        return False

def install_dependency(package_name, version=None):
    """Install a package using pip
    
    Args:
        package_name: The name of the package to install
        version: Specific version to install (optional)
        
    Returns:
        bool: True if installation was successful, False otherwise
    """
    try:
        package_spec = f"{package_name}=={version}" if version else package_name
        print(f"Installing {package_spec}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_spec])
        return True
    except subprocess.CalledProcessError:
        print(f"Failed to install {package_name}")
        return False

def ensure_dependencies():
    """Check and install required dependencies"""
    dependencies = {
        "pymupdf": "1.19.0",  # PyMuPDF (fitz)
        "pathlib": None,
    }
    
    print("Checking dependencies...")
    
    for package, version in dependencies.items():
        if not check_dependency(package, version):
            print(f"Installing {package}...")
            install_dependency(package, version)
    
    # Check for concurrent.futures, which is built-in to Python 3
    try:
        import concurrent.futures
        print("Found concurrent.futures (built-in module)")
    except ImportError:
        print("Warning: concurrent.futures not available. This should be built into Python 3.")
    
    # Check if tesseract is installed (for OCR support)
    try:
        import pytesseract
        print("Tesseract support available (for OCR)")
    except ImportError:
        print("Optional: pytesseract not found. OCR functionality will be limited.")
        print("To enable OCR, install Tesseract and pytesseract:")
        print("  pip install pytesseract")
        print("  Download and install Tesseract OCR from https://github.com/UB-Mannheim/tesseract/wiki")
    
    print("Dependency check complete.")

if __name__ == "__main__":
    ensure_dependencies() 