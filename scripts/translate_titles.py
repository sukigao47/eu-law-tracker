"""Translate public English titles into Chinese; retain original metadata."""
import hashlib
import json
import re
from pathlib import Path

def main():
    from argostranslate import package, translate
    installed = translate.get_installed_languages()
    if not any(x.code == "zh" for x in installed):
        package.update_package_index()
        model = next(p for p in package.get_available_packages() if p.from_code == "en" and p.to_code == "zh")
        package.install_from_path(model.download())
    cache_path = Path(".translation-cache/titles.json")
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    for path in [Path("site/data/catalog.json"), Path("site/data/related-materials.json")]:
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        count = 0
        for row in data["documents"]:
            title = row.get("title", "").strip()
            if not title:
                continue
            key = hashlib.sha256(title.encode()).hexdigest()
            result = cache.get(key)
            if not result:
                result = translate.translate(title, "en", "zh").strip()
                if not re.search(r"[\u3400-\u9fff]", result):
                    raise ValueError("No Chinese translation for " + row["id"])
                cache[key] = result
            row["titleZhFull"] = result
            row["titleZhSource"] = "machine_translation"
            count += 1
            if count % 20 == 0:
                cache_path.write_text(json.dumps(cache, ensure_ascii=False))
                print(f"{path}: translated {count}", flush=True)
        cache_path.write_text(json.dumps(cache, ensure_ascii=False))
        path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":"))+"\n")
        print(f"{path}: Chinese title coverage {count}/{len(data['documents'])}", flush=True)
        if count != len(data["documents"]):
            raise ValueError("Missing English titles; translation coverage incomplete")

if __name__ == "__main__":
    main()
