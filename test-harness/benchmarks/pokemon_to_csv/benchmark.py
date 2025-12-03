import csv
import os
import shutil
import difflib
import urllib.parse
import re
from collections import defaultdict

from lib.benchmark_base import BenchmarkBase
from typing import Any, Dict, Tuple
from io import StringIO

class Benchmark(BenchmarkBase):
    PASS_THRESHOLD = 0.9

    def __init__(self):
        # We assume the assets are in the same directory as this file, under assets/
        # But the base class expects the assets_dir path.
        # We can calculate it relative to this file.
        import os
        base_dir = os.path.dirname(os.path.abspath(__file__))
        assets_dir = os.path.join(base_dir, "assets")
        super().__init__("pokemon_card_lookup", assets_dir)

    def run(self, runner: Any, model: str, prompt_version: str) -> str:
        # The prompt from command_tester.py
        prompt = (
            "I need a list of the main, subsets and promotional sets of japanese pokemon card sets from this site, in csv format. "
            "Use the following column names: "
            "'Set,Era,Set No.,Symbol,Japanese Name,English Equivalent,No. of Cards,Release Date'. "
            "For example: \n"
            "```csv\n"
            "main,original,2,\"http://asset-server:8080/List of Japanese Pokémon Trading Card Game expansions - Bulbapedia, the community-driven Pokémon encyclopedia_files/SetSymbolJungle.png\",ポケモンジャングル Pokémon Jungle,Jungle,48,March 5, 1997\n"
            "subsets,scarlet & violet,3,\"http://asset-server:8080/List of Japanese Pokémon Trading Card Game expansions - Bulbapedia, the community-driven Pokémon encyclopedia_files/40px-SetSymbolRaging_Surf.png\",レイジングサーフRaging Surf\",\"⅓ of Paradox Rift,62 (30),September 22, 2023\n\""
            "```\n"
            "If a set doesn't have a column, you can ignore it. Symbol should be the url of the symbol image. "
            "Write to /workspace/test_area/jp_cards_all.csv. "
            "You may use the xpath tool to help you figure out what you need to extract. "
            "Ignore anything with the class 'roundy' in the html when extacting. The site is http://asset-server:8080/pokemon.html"
        )

        print(f"Using prompt {prompt}\n")
        print(f"Using path {self.input_path}\n")

        # Run the agent via the runner
        # We pass the input directory which contains pikachu.jpg
        # output = runner.run(prompt, self.input_path)

        output = runner.run(prompt, self.input_path)
        # output = "Big bubooty!!!"
        return output

    def verify(self, output: str) -> bool:
        print("Verifying output...\n")
        # Load in comparison csv
        expected_csv_path = self.assets_dir / "comparison/expected_jp_cards_all.csv"
        try:
            with open(expected_csv_path, 'r', encoding='utf-8') as f:
                expected_rows = list(csv.DictReader(f))
        except Exception as e:
            print(f"Error reading expected CSV: {e}")
            return False
            
        # Load in output csv
        output_csv_path = self.assets_dir / "input/jp_cards_all.csv"
        if not output_csv_path.exists():
            print("Output CSV file not found.")
            return False
            
        try:
            with open(output_csv_path, 'r', encoding='utf-8') as f:
                # Read header first to check columns
                reader = csv.DictReader(f)
                output_headers = reader.fieldnames
                output_rows = list(reader)
        except Exception as e:
            print(f"Error reading output CSV: {e}")
            return False

        # 1. Check Headers
        expected_headers = ["Set", "Era", "Set No.", "Symbol", "Japanese Name", "English Equivalent", "No. of Cards", "Release Date"]
        missing_headers = [h for h in expected_headers if h not in (output_headers or [])]
        
        if missing_headers:
            print(f"Missing headers: {missing_headers}")
            # Penalize heavily but continue to see if data exists
            header_score = 0.0
        else:
            header_score = 1.0

        # 2. Index Output Rows
        # Create a map of key -> row for fast lookup
        output_map = {}
        for row in output_rows:
            key = self.get_row_key(row)
            output_map[key] = row

        # 3. Score Rows
        total_rows = len(expected_rows)
        if total_rows == 0:
            print("No expected rows to compare.")
            return True

        row_scores = []
        column_scores = defaultdict(list)
        
        print(f"\nComparing {total_rows} rows...")
        
        for exp_row in expected_rows:
            key = self.get_row_key(exp_row)
            act_row = output_map.get(key)
            
            if not act_row:
                # Row missing
                row_scores.append(0.0)
                continue
            
            # Score each column
            current_row_scores = []
            
            # Symbol (URL)
            s_score = self.calculate_url_similarity(exp_row.get("Symbol", ""), act_row.get("Symbol", ""))
            column_scores["Symbol"].append(s_score)
            current_row_scores.append(s_score)
            
            # Text Columns
            for col in ["Japanese Name", "English Equivalent", "Release Date", "No. of Cards"]:
                score = self.calculate_similarity(exp_row.get(col, ""), act_row.get(col, ""))
                column_scores[col].append(score)
                current_row_scores.append(score)
            
            # Average score for this row
            row_scores.append(sum(current_row_scores) / len(current_row_scores))

        # 4. Calculate Final Scores
        avg_row_score = sum(row_scores) / total_rows
        final_score = (header_score * 0.2) + (avg_row_score * 0.8)
        
        print("\n" + "="*40)
        print(f"SCORING REPORT (Threshold: {self.PASS_THRESHOLD})")
        print("="*40)
        print(f"Header Score: {header_score:.2f}")
        print(f"Row Match Rate: {len([s for s in row_scores if s > 0])}/{total_rows}")
        print("-" * 20)
        print("Column Accuracy:")
        for col, scores in column_scores.items():
            avg_col = sum(scores) / len(scores) if scores else 0.0
            print(f"  {col:<20}: {avg_col:.2f}")
        print("-" * 20)
        print(f"Average Row Score: {avg_row_score:.2f}")
        print(f"FINAL SCORE:       {final_score:.2f}")
        print("="*40 + "\n")

        return final_score >= self.PASS_THRESHOLD

    def cleanup(self, output_path: str) -> None:
        # copy all output files from assets/input to output_path
        input_dir = self.assets_dir / "input"
        for file_name in os.listdir(input_dir):
            full_file_name = input_dir / file_name
            if os.path.isfile(full_file_name):
                shutil.copy(full_file_name, output_path)

        # Remove all files created in the test area
        test_area_path = self.assets_dir / "input"
        for file in test_area_path.iterdir():
            if file.is_file():
                file.unlink()

    def normalize_string(self, s: str) -> str:
        """Normalize string for comparison."""
        if not s:
            return ""
        # Remove "era" suffix if present (case insensitive)
        s = re.sub(r'\s*era\s*$', '', str(s), flags=re.IGNORECASE)
        # Normalize whitespace
        s = " ".join(str(s).split())
        return s.lower()

    def get_row_key(self, row: Dict[str, str]) -> Tuple[str, str, str]:
        """Generate a composite key for a row."""
        # Key based on Set, Era, and Set No.
        # Handle potential missing keys gracefully
        set_val = self.normalize_string(row.get("Set", ""))
        era_val = self.normalize_string(row.get("Era", ""))
        set_no_val = self.normalize_string(row.get("Set No.", ""))
        return (set_val, era_val, set_no_val)

    def calculate_similarity(self, a: str, b: str) -> float:
        """Calculate string similarity ratio."""
        return difflib.SequenceMatcher(None, self.normalize_string(a), self.normalize_string(b)).ratio()

    def calculate_url_similarity(self, url1: str, url2: str) -> float:
        """Calculate similarity between two URLs."""
        if not url1 or not url2:
            return 1.0 if not url1 and not url2 else 0.0
            
        # Parse URLs
        u1 = urllib.parse.urlparse(url1)
        u2 = urllib.parse.urlparse(url2)
        
        # Compare path and query (ignore scheme/netloc for less strict matching if needed, 
        # but here we probably want at least path matching)
        # We can be lenient on the domain if it's just a local vs remote thing, 
        # but the prompt asks for specific URLs.
        # Let's check path similarity primarily.
        
        path1 = urllib.parse.unquote(u1.path)
        path2 = urllib.parse.unquote(u2.path)
        
        # Simple filename check might be enough?
        # "SetSymbolJungle.png"
        file1 = os.path.basename(path1)
        file2 = os.path.basename(path2)
        
        if file1 == file2:
            return 1.0
            
        return self.calculate_similarity(path1, path2)
