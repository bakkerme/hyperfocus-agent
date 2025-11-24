import csv
import os
import shutil

from lib.benchmark_base import BenchmarkBase
from typing import Any
from io import StringIO

class Benchmark(BenchmarkBase):
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
            "'Era,Set No.,Symbol,Japanese Name,English Equivalent,No. of Cards,Release Date'. "
            "For example: \n"
            "```csv\n"
            "original,2,\"http://asset-server:8080/List%20of%20Japanese%20Pok%C3%A9mon%20Trading%20Card%20Game%20expansions%20-%20Bulbapedia,%20the%20community-driven%20Pok%C3%A9mon%20encyclopedia_files/SetSymbolJungle.png/SetSymbolJungle.png\",ポケモンジャングル (Pokémon Jungle),Jungle,48,\"March 5, 1997\"\n"
            "```\n"
            "If a set doesn't have a column, you can ignore it. Symbol should be the url of the symbol image. "
            "Write to /workspace/test_area/jp_cards_all.csv. "
            "Ignore anything with the class 'roundy' in the html when extacting. The site is http://asset-server:8080/pokemon.html"
        )

        print(f"Using prompt {prompt}\n")
        print(f"Using path {self.input_path}\n")

        # Run the agent via the runner
        # We pass the input directory which contains pikachu.jpg
        output = runner.run(prompt, self.input_path)
        return output

    def verify(self, output: str) -> bool:
        # Load in comparison csv
        expected_csv_path = self.assets_dir / "comparison/expected_jp_cards_all.csv"
        with open(expected_csv_path, 'r', encoding='utf-8') as f:
            expected_csv = f.read()
            
        try:
            # Load in output csv
            output_csv_path = self.assets_dir / "input/jp_cards_all.csv"
            with open(output_csv_path, 'r', encoding='utf-8') as f:
                output_csv = f.read()
        except FileNotFoundError:
            # if the output doesn't exist, that's a failure
            output_csv = None
            print("Output CSV file not found.")
            return False
        
        # if the file is empty, that's a failure
        if not output_csv or output_csv.strip() == "":
            print("Output CSV file is empty.")
            return False

        # if the csv doesn't parse, that's a failure
        try:
            expected_rows = list(csv.reader(StringIO(expected_csv)))
            output_rows = list(csv.reader(StringIO(output_csv)))
        except Exception:
            print("CSV parsing failed.")
            return False
        
        # Compare number of rows
        if len(expected_rows) != len(output_rows):
            print("Number of rows in CSV do not match.")
            return False

        # Compare each row
        for i in range(len(expected_rows)):
            if expected_rows[i] != output_rows[i]:
                print(f"Row {i} does not match.")
                return False
                
        return True

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
