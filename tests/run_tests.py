#!/usr/bin/env python3
"""
Test runner for running all unit tests
"""
import unittest
import os
import sys

def run_all_tests():
    """Run all unit tests in the unit directory"""
    # Add the root directory to path
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    sys.path.insert(0, root_dir)
    
    # Discover and run all tests
    test_loader = unittest.TestLoader()
    test_suite = test_loader.discover(os.path.join(os.path.dirname(__file__), 'unit'), pattern='test_*.py')
    
    # Create test runner
    test_runner = unittest.TextTestRunner(verbosity=2)
    result = test_runner.run(test_suite)
    
    # Return success/failure
    return len(result.errors) == 0 and len(result.failures) == 0

if __name__ == "__main__":
    print("Running all tests...")
    success = run_all_tests()
    sys.exit(0 if success else 1) 