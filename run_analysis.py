from pathlib import Path
import json
from src.analysis import run

if __name__ == '__main__':
    _, summary, _, _ = run(Path(__file__).resolve().parent)
    print(json.dumps(summary,ensure_ascii=False,indent=2))
