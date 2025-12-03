#!/usr/bin/env python3
"""
Standalone test script for pokemon_to_csv benchmark verification.

Usage:
    python tests/test_pokemon_csv_verify.py <assets_dir>

Example:
    python tests/test_pokemon_csv_verify.py test-harness/benchmarks/pokemon_to_csv/assets
"""

import sys
from pathlib import Path

# Add test-harness to path so we can import benchmark modules
test_harness_path = Path(__file__).parent.parent / "test-harness" / "benchmarks"
sys.path.insert(0, str(test_harness_path))

from pokemon_to_csv.benchmark import Benchmark


def test_verify(assets_dir: str):
    """Test the verify method with a custom assets directory."""
    assets_path = Path(assets_dir).resolve()
    
    if not assets_path.exists():
        print(f"Error: Assets directory does not exist: {assets_path}")
        return False
    
    print(f"Testing verification with assets_dir: {assets_path}")
    print(f"  - Expected CSV: {assets_path / 'comparison/expected_jp_cards_all.csv'}")
    print(f"  - Output CSV:   {assets_path / 'input/jp_cards_all.csv'}")
    print()
    
    # Create benchmark instance
    benchmark = Benchmark()
    
    # Override the assets_dir to use our test directory
    benchmark.assets_dir = assets_path
    benchmark.input_path = assets_path / "input"
    benchmark.comparison_path = assets_path / "comparison"
    
    # Run verification (output parameter is not used by this benchmark's verify)
    try:
        result = benchmark.verify("")
        print()
        print("="*60)
        if result:
            print("✓ VERIFICATION PASSED")
        else:
            print("✗ VERIFICATION FAILED")
        print("="*60)
        return result
    except Exception as e:
        print()
        print("="*60)
        print(f"✗ VERIFICATION ERROR: {e}")
        print("="*60)
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    
    assets_dir = sys.argv[1]
    success = test_verify(assets_dir)
    sys.exit(0 if success else 1)
