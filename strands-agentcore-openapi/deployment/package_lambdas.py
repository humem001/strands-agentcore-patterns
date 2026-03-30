#!/usr/bin/env python3
"""
Package Lambda functions for deployment.

This script packages the Agent Lambda with its dependencies
into a deployment-ready ZIP file.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


def clean_directory(path: Path) -> None:
    """Remove directory if it exists."""
    if path.exists():
        print(f"  Removing existing directory: {path}")
        shutil.rmtree(path)


def copy_dependencies(package_dir: Path, deps_dir: Path) -> bool:
    """Copy pre-built dependencies to package directory."""
    if not deps_dir.exists():
        print(f"  Installing dependencies with pip...")
        # Install dependencies directly into package directory
        # IMPORTANT: Use --python-version to match Lambda runtime (Python 3.12)
        result = subprocess.run(
            [
                sys.executable, "-m", "pip", "install",
                "-r", "requirements.txt",
                "-t", str(package_dir),
                "--platform", "manylinux2014_x86_64",
                "--python-version", "3.12",
                "--only-binary=:all:",
                "--upgrade"
            ],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"  ✗ Failed to install dependencies: {result.stderr}")
            return False
        
        print("  ✓ Dependencies installed")
        return True
    
    # Copy pre-built dependencies
    print(f"  Copying pre-built dependencies from {deps_dir}...")
    for item in deps_dir.iterdir():
        if item.name not in ['__pycache__', '.DS_Store', 'bin']:
            dst = package_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dst)
    
    print("  ✓ Dependencies copied")
    return True


def copy_source_modules(package_dir: Path, modules: List[str]) -> bool:
    """Copy source modules to package directory."""
    src_dir = Path("src")
    
    for module in modules:
        module_src = src_dir / module
        if not module_src.exists():
            print(f"  ✗ Source module not found: {module_src}")
            return False
        
        module_dst = package_dir / module
        print(f"  Copying {module_src} -> {module_dst}")
        shutil.copytree(module_src, module_dst, dirs_exist_ok=True)
    
    print("  ✓ Source code copied")
    return True


def cleanup_package(package_dir: Path) -> None:
    """Remove unnecessary files from package."""
    print("  Cleaning up unnecessary files...")
    
    patterns_to_remove = [
        "**/__pycache__",
        "**/*.pyc",
        "**/*.pyo",
        # NOTE: Do NOT remove .dist-info — opentelemetry uses entry_points()
        # which requires dist-info metadata to discover context providers.
        # Removing .dist-info causes StopIteration on Lambda import.
        "**/*.egg-info",
        "**/tests",
        "**/.pytest_cache",
        "**/test_*.py",
        "**/*_test.py"
    ]
    
    for pattern in patterns_to_remove:
        for path in package_dir.glob(pattern):
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
    
    print("  ✓ Cleanup complete")


def create_zip(package_dir: Path, zip_name: str) -> Tuple[bool, float]:
    """Create ZIP file from package directory."""
    print(f"  Creating {zip_name}...")
    
    zip_path = Path(zip_name)
    if zip_path.exists():
        zip_path.unlink()
    
    shutil.make_archive(
        zip_name.replace('.zip', ''),
        'zip',
        package_dir
    )
    
    if not zip_path.exists():
        print(f"  ✗ Failed to create {zip_name}")
        return False, 0.0
    
    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"  ✓ Created {zip_name} ({size_mb:.2f} MB)")
    
    return True, size_mb


def verify_package(zip_name: str, required_files: List[str]) -> bool:
    """Verify package contains required files."""
    print(f"  Verifying {zip_name}...")
    
    result = subprocess.run(
        ["unzip", "-l", zip_name],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"  ✗ Failed to list ZIP contents")
        return False
    
    for required_file in required_files:
        if required_file not in result.stdout:
            print(f"  ✗ Missing required file: {required_file}")
            return False
    
    print(f"  ✓ Package structure verified")
    return True


def package_agent_lambda() -> bool:
    """Package Agent Lambda with dependencies."""
    print("\n" + "=" * 60)
    print("PACKAGING AGENT LAMBDA")
    print("=" * 60)
    
    package_dir = Path("deployment/agent-lambda-package")
    deps_dir = Path("agent-lambda-deps")
    zip_name = "deployment/agent-lambda.zip"
    
    # Clean previous package
    clean_directory(package_dir)
    
    # Create package directory
    print(f"\nCreating package directory: {package_dir}")
    package_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy dependencies
    print("\nCopying dependencies...")
    if not copy_dependencies(package_dir, deps_dir):
        return False
    
    # Copy source modules
    print("\nCopying source code...")
    if not copy_source_modules(package_dir, ["agent", "shared"]):
        return False
    
    # Cleanup
    print("\nCleaning up...")
    cleanup_package(package_dir)
    
    # Create ZIP
    print("\nCreating deployment package...")
    success, size_mb = create_zip(package_dir, zip_name)
    if not success:
        return False
    
    # Verify
    print("\nVerifying package...")
    if not verify_package(zip_name, ["agent/handler.py", "shared/"]):
        return False
    
    print("\n" + "=" * 60)
    print("✓ AGENT LAMBDA PACKAGED")
    print("=" * 60)
    print(f"Package: {zip_name}")
    print(f"Size: {size_mb:.2f} MB")
    
    return True






def main():
    """Package Agent Lambda."""
    print("=" * 60)
    print("OPENAPI AGENT GATEWAY - LAMBDA PACKAGING")
    print("=" * 60)
    
    # Ensure deployment directory exists
    Path("deployment").mkdir(exist_ok=True)
    
    if not package_agent_lambda():
        print("\n✗ Failed to package Agent Lambda")
        return False
    
    print("\n" + "=" * 60)
    print("✓ LAMBDA PACKAGED")
    print("=" * 60)
    print("\nDeployment package: deployment/agent-lambda.zip")
    print("\nNext step: python update_lambda_code.py")
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
