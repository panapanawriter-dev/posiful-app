import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from posiful.history import generate_sample, SAMPLE_PATH, generate_menu_plan, PLAN_PATH

if __name__ == '__main__':
    sample = generate_sample()
    SAMPLE_PATH.parent.mkdir(parents=True,exist_ok=True)
    SAMPLE_PATH.write_text(json.dumps(sample,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    PLAN_PATH.write_text(json.dumps(generate_menu_plan(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(sample['metadata'],ensure_ascii=True))
