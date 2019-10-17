from pathlib import Path
def load_text(fpath):
    return Path(fpath).read_text(encoding='utf-8')