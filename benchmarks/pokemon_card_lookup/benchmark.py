from lib.benchmark_base import BenchmarkBase
from typing import Any
import shutil
import os

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
        # copy pikachu.jpg to the input directory
        source_image_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "pikachu.jpg")
        dest_image_path = os.path.join(self.input_path, "pikachu.jpg")
        shutil.copyfile(source_image_path, dest_image_path)

        # The prompt from command_tester.py
        prompt = (
            "Load pikachu.jpg and describe the card content, then look up the card symbol, "
            "(it will be a small string of up to 4 characters, like 'cpa4', in the bottom left corner, nothing else, no spaces) "
            "and look it up in the provided website and "
            "include the set name alongside the card content. Make sure to get an exact match on "
            "the code, since there are sets and subsets that have similar codes. "
            "http://asset-server:8080/pokemon.html"
        )

        print(f"Using prompt {prompt}\n")
        print(f"Using path {self.input_path}\n")

        # Run the agent via the runner
        # We pass the input directory which contains pikachu.jpg
        output = runner.run(prompt, self.input_path)
        return output

    def verify(self, output: str) -> bool:
        # Verification logic from command_tester.py: search for '151'
        return '151' in output

    def cleanup(self) -> None:
        # Clean up any files created in the test area
        test_area_path = self.assets_dir / "input"
        for file in test_area_path.iterdir():
            if file.is_file():
                file.unlink()