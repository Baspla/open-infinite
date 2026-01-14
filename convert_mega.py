import argparse
import ast
import json
import os
import sys
from typing import Dict, Tuple, Any


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


def _parse_combo_key(raw_key: str) -> Tuple[str, str]:
    """Parse keys like "('Water', 'Fire')" into two item strings."""
    try:
        pair = ast.literal_eval(raw_key)
    except Exception:
        print(f"Skipping combo key {raw_key!r}: not a valid literal tuple", file=sys.stderr)
        return "", ""

    if not (isinstance(pair, (list, tuple)) and len(pair) == 2):
        print(f"Skipping combo key {raw_key!r}: expected a pair", file=sys.stderr)
        return "", ""

    first, second = pair
    if not isinstance(first, str) or not isinstance(second, str):
        print(f"Skipping combo key {raw_key!r}: pair must contain strings", file=sys.stderr)
        return "", ""

    return first, second


def _merge_combos(cache_data: Dict[str, Any], combocache: Dict[str, str]) -> int:
    new_combos = 0
    for raw_key, result in cache_data.items():
        if not isinstance(result, str):
            print(f"Skipping combo {raw_key!r}: result is not a string", file=sys.stderr)
            continue

        item1, item2 = _parse_combo_key(raw_key)
        if not item1 and not item2:
            continue

        key = _normalize_key(item1, item2)
        existing = combocache.get(key)
        if existing and existing != result:
            print(
                f"Conflict for {key!r}: keeping existing result {existing!r}, "
                f"skipping new result {result!r}",
                file=sys.stderr,
            )
            continue

        if not existing:
            new_combos += 1
        combocache[key] = result
    return new_combos


def _merge_items(meta_store: Dict[str, Any], itemcache: Dict[str, Any]) -> Tuple[int, int]:
    new_items = 0
    updated_emojis = 0

    for name, meta in meta_store.items():
        if not isinstance(name, str):
            print(f"Skipping meta entry with non-string name {name!r}", file=sys.stderr)
            continue
        emoji = None
        if isinstance(meta, dict):
            value = meta.get("emoji")
            if isinstance(value, str) and value:
                emoji = value
        if name not in itemcache:
            itemcache[name] = emoji
            new_items += 1
        elif emoji and itemcache.get(name) in (None, ""):
            itemcache[name] = emoji
            updated_emojis += 1
    return new_items, updated_emojis


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert mega.sav JSON (cache/meta_store) into separate combo and item cache JSON files.",
    )
    parser.add_argument("--mega", default="mega.sav", help="Path to the mega.sav JSON file")
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

    try:
        with open(args.mega, "r", encoding="utf-8") as fh:
            mega_data = json.load(fh)
    except FileNotFoundError:
        print(f"No such file: {args.mega}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"Error decoding JSON from {args.mega}: {exc}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(mega_data, dict):
        print(f"Unexpected JSON structure in {args.mega}: expected an object", file=sys.stderr)
        sys.exit(1)

    cache_data = mega_data.get("cache") or {}
    meta_store = mega_data.get("meta_store") or {}
    if not isinstance(cache_data, dict):
        print(f"Ignoring cache section: expected an object", file=sys.stderr)
        cache_data = {}
    if not isinstance(meta_store, dict):
        print(f"Ignoring meta_store section: expected an object", file=sys.stderr)
        meta_store = {}

    combocache = _load_mapping(args.combo_cache)
    itemcache = _load_mapping(args.item_cache)

    new_combos = _merge_combos(cache_data, combocache)
    new_items, updated_emojis = _merge_items(meta_store, itemcache)

    combo_output = args.combo_output or args.combo_cache
    item_output = args.item_output or args.item_cache
    _write_mapping(combo_output, combocache)
    _write_mapping(item_output, itemcache)

    print(
        f"Done. Added {new_combos} combo entries, {new_items} new items, and "
        f"updated {updated_emojis} emojis. Wrote {len(combocache)} combos to {combo_output} "
        f"and {len(itemcache)} items to {item_output}.",
    )


if __name__ == "__main__":
    main()
