import argparse
import json
import os
import sys
from typing import Any, Dict, Tuple


def _normalize_key(item1: str, item2: str) -> str:
    """Match the in-game combo key format: lowercase, sorted, pipe-delimited."""
    a = (item1 or "").strip().lower()
    b = (item2 or "").strip().lower()
    first, second = sorted([a, b])
    return f"{first}|{second}"


def _load_mapping(path: str) -> Dict[str, Any]:
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return data
        print(f"Skipping {path}: expected a JSON object", file=sys.stderr)
    return {}


def _write_mapping(path: str, mapping: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(mapping, fh, ensure_ascii=True, indent=2)


def _process_words(words_path: str, combocache: Dict[str, Any], itemcache: Dict[str, Any]) -> Tuple[int, int]:
    new_combos = 0
    new_items = 0
    with open(words_path, "r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("=")]
            if len(parts) != 3:
                print(f"Skipping line {lineno}: expected 3 fields, got {len(parts)}", file=sys.stderr)
                continue
            item1, item2, result = parts
            if not item1 or not item2 or not result:
                print(f"Skipping line {lineno}: empty value(s)", file=sys.stderr)
                continue

            key = _normalize_key(item1, item2)
            existing = combocache.get(key)
            if existing and existing != result:
                print(
                    f"Conflict on line {lineno} for {key!r}: overriding existing result {existing!r} "
                    f"with {result!r}",
                    file=sys.stderr,
                )
                combocache[key] = result
            elif not existing:
                combocache[key] = result
                new_combos += 1

            if result not in itemcache:
                itemcache[result] = None
                new_items += 1
    return new_combos, new_items


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert words.csv (itemA=itemB=itemResult) into separate combo and item cache JSON files."
    )
    parser.add_argument("--words", default="words.csv", help="Path to the source words.csv file")
    parser.add_argument(
        "--combo-cache",
        default="cache/combocache.json",
        help="Existing combo cache JSON to merge into (read if present)",
    )
    parser.add_argument(
        "--item-cache",
        default="cache/itemcache.json",
        help="Existing item cache JSON to merge into (read if present)",
    )
    parser.add_argument(
        "--combo-output",
        default=None,
        help="Path to write the combo cache JSON (default: overwrite --combo-cache)",
    )
    parser.add_argument(
        "--item-output",
        default=None,
        help="Path to write the item cache JSON (default: overwrite --item-cache)",
    )
    args = parser.parse_args()

    combocache = _load_mapping(args.combo_cache)
    itemcache = _load_mapping(args.item_cache)
    new_combos, new_items = _process_words(args.words, combocache, itemcache)

    combo_output = args.combo_output or args.combo_cache
    item_output = args.item_output or args.item_cache
    _write_mapping(combo_output, combocache)
    _write_mapping(item_output, itemcache)

    print(
        f"Done. Added {new_combos} combo entries and {new_items} item entries. "
        f"Wrote {len(combocache)} combos to {combo_output} and {len(itemcache)} items to {item_output}"
    )


if __name__ == "__main__":
    main()
