"""
FIX 2.19: Test runner and coverage reporting
Defines how to run test suite and check coverage
"""

import subprocess
import sys

def run_tests():
    """Run test suite with coverage"""
    cmd = [
        sys.executable, "-m", "pytest", 
        "tests/",
        "--cov=services",
        "--cov=models", 
        "--cov-report=html",
        "--cov-report=term-missing",
        "-v"
    ]
    result = subprocess.run(cmd, cwd="backend")
    return result.returncode

def run_tests_ci():
    """Run tests in CI mode (fail on coverage)"""
    cmd = [
        sys.executable, "-m", "pytest", 
        "tests/",
        "--cov=services",
        "--cov=models",
        "--cov-fail-under=80",
        "-v",
        "--tb=short"
    ]
    result = subprocess.run(cmd, cwd="backend")
    return result.returncode

if __name__ == "__main__":
    sys.exit(run_tests())
