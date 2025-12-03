"""Tests for the benchmark scoring logic."""
import pytest
import csv
import tempfile
import os
import sys
from pathlib import Path

# Add test-harness and its benchmarks directory to path
test_harness_path = Path(__file__).parent.parent / "test-harness"
benchmarks_path = test_harness_path / "benchmarks"
if str(test_harness_path) not in sys.path:
    sys.path.insert(0, str(test_harness_path))
if str(benchmarks_path) not in sys.path:
    sys.path.insert(0, str(benchmarks_path))

from benchmarks.pokemon_to_csv.benchmark import Benchmark


@pytest.fixture
def benchmark():
    """Create a benchmark instance for testing."""
    return Benchmark()


@pytest.fixture
def temp_csv_files():
    """Create temporary CSV files for testing."""
    temp_dir = tempfile.mkdtemp()
    
    expected_path = Path(temp_dir) / "expected.csv"
    output_path = Path(temp_dir) / "output.csv"
    
    yield expected_path, output_path
    
    # Cleanup
    if expected_path.exists():
        expected_path.unlink()
    if output_path.exists():
        output_path.unlink()
    os.rmdir(temp_dir)


class TestStringNormalization:
    """Test string normalization functions."""
    
    def test_normalize_string_basic(self, benchmark):
        assert benchmark.normalize_string("Hello World") == "hello world"
    
    def test_normalize_string_era_suffix(self, benchmark):
        assert benchmark.normalize_string("Scarlet & Violet Era") == "scarlet & violet"
        assert benchmark.normalize_string("scarlet & violet era") == "scarlet & violet"
        assert benchmark.normalize_string("SCARLET & VIOLET ERA") == "scarlet & violet"
    
    def test_normalize_string_whitespace(self, benchmark):
        assert benchmark.normalize_string("  Multiple   Spaces  ") == "multiple spaces"
        assert benchmark.normalize_string("\tTabs\tand\tNewlines\n") == "tabs and newlines"
    
    def test_normalize_string_empty(self, benchmark):
        assert benchmark.normalize_string("") == ""
        assert benchmark.normalize_string(None) == ""


class TestRowKey:
    """Test row key generation."""
    
    def test_get_row_key_complete(self, benchmark):
        row = {
            "Set": "Main",
            "Era": "Original",
            "Set No.": "1"
        }
        key = benchmark.get_row_key(row)
        assert key == ("main", "original", "1")
    
    def test_get_row_key_missing_fields(self, benchmark):
        row = {
            "Set": "Main"
        }
        key = benchmark.get_row_key(row)
        assert key == ("main", "", "")
    
    def test_get_row_key_normalization(self, benchmark):
        row = {
            "Set": "Main Era",
            "Era": "Original Era",
            "Set No.": "  1  "
        }
        key = benchmark.get_row_key(row)
        assert key == ("main", "original", "1")


class TestSimilarityCalculations:
    """Test similarity calculation functions."""
    
    def test_calculate_similarity_identical(self, benchmark):
        score = benchmark.calculate_similarity("Hello World", "Hello World")
        assert score == 1.0
    
    def test_calculate_similarity_different(self, benchmark):
        score = benchmark.calculate_similarity("Hello", "Goodbye")
        assert score < 1.0
        assert score >= 0.0
    
    def test_calculate_similarity_case_insensitive(self, benchmark):
        score = benchmark.calculate_similarity("Hello World", "hello world")
        assert score == 1.0
    
    def test_calculate_similarity_partial_match(self, benchmark):
        score = benchmark.calculate_similarity("Pokémon Jungle", "Pokemon Jungle Set")
        assert score > 0.5
        assert score < 1.0
    
    def test_calculate_url_similarity_identical_filenames(self, benchmark):
        url1 = "http://server1.com/path/to/image.png"
        url2 = "http://server2.com/different/path/image.png"
        score = benchmark.calculate_url_similarity(url1, url2)
        assert score == 1.0
    
    def test_calculate_url_similarity_different_filenames(self, benchmark):
        url1 = "http://server.com/path/image1.png"
        url2 = "http://server.com/path/image2.png"
        score = benchmark.calculate_url_similarity(url1, url2)
        assert score < 1.0
    
    def test_calculate_url_similarity_empty(self, benchmark):
        # Both empty should be 1.0 (perfect match)
        assert benchmark.calculate_url_similarity("", "") == 1.0
        
        # One empty should be 0.0
        assert benchmark.calculate_url_similarity("http://example.com/image.png", "") == 0.0
        assert benchmark.calculate_url_similarity("", "http://example.com/image.png") == 0.0
    
    def test_calculate_url_similarity_encoded_paths(self, benchmark):
        url1 = "http://server.com/path%20with%20spaces/image.png"
        url2 = "http://server.com/different/image.png"
        score = benchmark.calculate_url_similarity(url1, url2)
        assert score == 1.0


class TestScoringLogic:
    """Test the overall scoring logic."""
    
    def test_perfect_match_headers_and_rows(self, benchmark, temp_csv_files):
        """Test that identical CSVs get a perfect score."""
        expected_path, output_path = temp_csv_files
        
        # Create identical CSVs
        data = [
            ["Set", "Era", "Set No.", "Symbol", "Japanese Name", "English Equivalent", "No. of Cards", "Release Date"],
            ["main", "original", "1", "http://example.com/symbol1.png", "ポケモン", "Pokemon", "102", "October 20, 1996"],
            ["main", "original", "2", "http://example.com/symbol2.png", "ジャングル", "Jungle", "48", "March 5, 1997"],
        ]
        
        with open(expected_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(data)
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(data)
        
        # Manually read and compare
        with open(expected_path, 'r', encoding='utf-8') as f:
            expected_rows = list(csv.DictReader(f))
        
        with open(output_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            output_headers = reader.fieldnames
            output_rows = list(reader)
        
        # Check headers
        expected_headers = ["Set", "Era", "Set No.", "Symbol", "Japanese Name", "English Equivalent", "No. of Cards", "Release Date"]
        missing_headers = [h for h in expected_headers if h not in (output_headers or [])]
        header_score = 0.0 if missing_headers else 1.0
        
        # Create output map
        output_map = {}
        for row in output_rows:
            key = benchmark.get_row_key(row)
            output_map[key] = row
        
        # Score rows
        total_rows = len(expected_rows)
        row_scores = []
        
        for exp_row in expected_rows:
            key = benchmark.get_row_key(exp_row)
            act_row = output_map.get(key)
            
            if not act_row:
                row_scores.append(0.0)
                continue
            
            current_row_scores = []
            
            # Symbol
            s_score = benchmark.calculate_url_similarity(exp_row.get("Symbol", ""), act_row.get("Symbol", ""))
            current_row_scores.append(s_score)
            
            # Text columns
            for col in ["Japanese Name", "English Equivalent", "Release Date", "No. of Cards"]:
                score = benchmark.calculate_similarity(exp_row.get(col, ""), act_row.get(col, ""))
                current_row_scores.append(score)
            
            row_scores.append(sum(current_row_scores) / len(current_row_scores))
        
        avg_row_score = sum(row_scores) / total_rows
        final_score = (header_score * 0.2) + (avg_row_score * 0.8)
        
        assert final_score == 1.0
    
    def test_missing_headers_penalty(self, benchmark, temp_csv_files):
        """Test that missing headers reduce the score."""
        expected_path, output_path = temp_csv_files
        
        # Expected has all headers
        expected_data = [
            ["Set", "Era", "Set No.", "Symbol", "Japanese Name", "English Equivalent", "No. of Cards", "Release Date"],
            ["main", "original", "1", "http://example.com/symbol1.png", "ポケモン", "Pokemon", "102", "October 20, 1996"],
        ]
        
        # Output missing some headers
        output_data = [
            ["Set", "Era", "Set No.", "Japanese Name"],
            ["main", "original", "1", "ポケモン"],
        ]
        
        with open(expected_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(expected_data)
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(output_data)
        
        # Manually calculate score
        with open(expected_path, 'r', encoding='utf-8') as f:
            expected_rows = list(csv.DictReader(f))
        
        with open(output_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            output_headers = reader.fieldnames
            output_rows = list(reader)
        
        expected_headers = ["Set", "Era", "Set No.", "Symbol", "Japanese Name", "English Equivalent", "No. of Cards", "Release Date"]
        missing_headers = [h for h in expected_headers if h not in (output_headers or [])]
        
        # Should have missing headers
        assert len(missing_headers) > 0
        header_score = 0.0
        
        # Calculate final score (should be less than perfect due to header penalty)
        # Even if row data is perfect, header_score of 0 * 0.2 = 0 contribution
        # So max score would be 0.8 (if all row data perfect)
        output_map = {}
        for row in output_rows:
            key = benchmark.get_row_key(row)
            output_map[key] = row
        
        row_scores = []
        for exp_row in expected_rows:
            key = benchmark.get_row_key(exp_row)
            act_row = output_map.get(key)
            
            if not act_row:
                row_scores.append(0.0)
                continue
            
            current_row_scores = []
            s_score = benchmark.calculate_url_similarity(exp_row.get("Symbol", ""), act_row.get("Symbol", ""))
            current_row_scores.append(s_score)
            
            for col in ["Japanese Name", "English Equivalent", "Release Date", "No. of Cards"]:
                score = benchmark.calculate_similarity(exp_row.get(col, ""), act_row.get(col, ""))
                current_row_scores.append(score)
            
            row_scores.append(sum(current_row_scores) / len(current_row_scores))
        
        avg_row_score = sum(row_scores) / len(row_scores)
        final_score = (header_score * 0.2) + (avg_row_score * 0.8)
        
        assert final_score < 1.0
        assert final_score <= 0.8  # Max possible with header_score = 0
    
    def test_missing_rows_penalty(self, benchmark, temp_csv_files):
        """Test that missing rows reduce the score."""
        expected_path, output_path = temp_csv_files
        
        headers = ["Set", "Era", "Set No.", "Symbol", "Japanese Name", "English Equivalent", "No. of Cards", "Release Date"]
        
        # Expected has 3 rows
        expected_data = [
            headers,
            ["main", "original", "1", "http://example.com/symbol1.png", "ポケモン", "Pokemon", "102", "October 20, 1996"],
            ["main", "original", "2", "http://example.com/symbol2.png", "ジャングル", "Jungle", "48", "March 5, 1997"],
            ["main", "original", "3", "http://example.com/symbol3.png", "化石", "Fossil", "48", "June 27, 1997"],
        ]
        
        # Output only has 1 row
        output_data = [
            headers,
            ["main", "original", "1", "http://example.com/symbol1.png", "ポケモン", "Pokemon", "102", "October 20, 1996"],
        ]
        
        with open(expected_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(expected_data)
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(output_data)
        
        # Calculate score
        with open(expected_path, 'r', encoding='utf-8') as f:
            expected_rows = list(csv.DictReader(f))
        
        with open(output_path, 'r', encoding='utf-8') as f:
            output_rows = list(csv.DictReader(f))
        
        output_map = {}
        for row in output_rows:
            key = benchmark.get_row_key(row)
            output_map[key] = row
        
        row_scores = []
        for exp_row in expected_rows:
            key = benchmark.get_row_key(exp_row)
            act_row = output_map.get(key)
            
            if not act_row:
                row_scores.append(0.0)
                continue
            
            current_row_scores = []
            s_score = benchmark.calculate_url_similarity(exp_row.get("Symbol", ""), act_row.get("Symbol", ""))
            current_row_scores.append(s_score)
            
            for col in ["Japanese Name", "English Equivalent", "Release Date", "No. of Cards"]:
                score = benchmark.calculate_similarity(exp_row.get(col, ""), act_row.get(col, ""))
                current_row_scores.append(score)
            
            row_scores.append(sum(current_row_scores) / len(current_row_scores))
        
        avg_row_score = sum(row_scores) / len(row_scores)
        
        # Should have 2 missing rows (score 0.0) and 1 perfect row (score 1.0)
        # Average = (1.0 + 0.0 + 0.0) / 3 = 0.333...
        assert avg_row_score < 0.5
    
    def test_partial_similarity_in_text_fields(self, benchmark, temp_csv_files):
        """Test that similar but not identical text gets partial credit."""
        expected_path, output_path = temp_csv_files
        
        headers = ["Set", "Era", "Set No.", "Symbol", "Japanese Name", "English Equivalent", "No. of Cards", "Release Date"]
        
        expected_data = [
            headers,
            ["main", "original", "1", "http://example.com/symbol1.png", "ポケモンジャングル", "Jungle", "48", "March 5, 1997"],
        ]
        
        # Output has slightly different Japanese name
        output_data = [
            headers,
            ["main", "original", "1", "http://example.com/symbol1.png", "ポケモン ジャングル", "Jungle", "48", "March 5, 1997"],
        ]
        
        with open(expected_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(expected_data)
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(output_data)
        
        # Calculate score
        with open(expected_path, 'r', encoding='utf-8') as f:
            expected_rows = list(csv.DictReader(f))
        
        with open(output_path, 'r', encoding='utf-8') as f:
            output_rows = list(csv.DictReader(f))
        
        exp_row = expected_rows[0]
        act_row = output_rows[0]
        
        # Test the specific similarity
        jp_score = benchmark.calculate_similarity(exp_row["Japanese Name"], act_row["Japanese Name"])
        
        # Should get high but not perfect score
        assert jp_score > 0.8
        assert jp_score < 1.0
