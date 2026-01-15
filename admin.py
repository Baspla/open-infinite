"""Interactive admin CLI for the game server.

Run inside the container to query and manage the running server. Uses the
/admin HTTP endpoints exposed by server.py. Authenticate with the
ADMIN_TOKEN environment variable if set on the server.
"""
import os
import sys
from typing import Optional, Any, Dict

import httpx

DEFAULT_BASE_URL = "http://localhost:8080"


def _build_client(base_url: str, token: Optional[str]) -> httpx.Client:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.Client(base_url=base_url, headers=headers, timeout=10.0)


def _print_users(users):
    if not users:
        print("No users connected.")
        return
    print("Connected users:")
    for entry in users:
        uuid = entry.get("uuid", "?")
        name = entry.get("name", "?")
        print(f"- {name} ({uuid})")


def _request(client: httpx.Client, method: str, path: str, payload=None):
    try:
        response = client.request(method, path, json=payload)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        text = exc.response.text.strip()
        print(f"Server error {exc.response.status_code}: {text or 'no body'}")
    except httpx.RequestError as exc:
        print(f"Request failed: {exc}")
    return None


def show_status(client: httpx.Client):
    data = _request(client, "GET", "/admin/status")
    if not isinstance(data, dict):
        return
    print(f"Gamemode: {data.get('gamemode', 'unknown')}")
    _print_users(data.get("users") or [])


def list_users(client: httpx.Client):
    data = _request(client, "GET", "/admin/users")
    if not isinstance(data, dict):
        return
    _print_users(data.get("users") or [])


def _prompt_bingo_config(mode: str) -> Dict[str, Any]:
    """Collect bingo-style config options from stdin."""
    config: Dict[str, Any] = {}

    timer_str = input("Timer seconds (default 900): ").strip()
    if timer_str:
        try:
            config["timer"] = int(timer_str)
        except ValueError:
            print("Invalid timer, using default.")

    size_str = input("Bingo size (default 5): ").strip()
    if size_str:
        try:
            config["size"] = int(size_str)
        except ValueError:
            print("Invalid size, using default.")

    words_input = input("Comma-separated words (optional, leave empty for random): ").strip()
    if words_input:
        words = [w.strip() for w in words_input.split(",") if w.strip()]
        if words:
            config["words"] = words

    manual_input = input("Manual mode (click to mark)? (y/n, default y): ").strip().lower()
    config["manual"] = not (manual_input in ('n', 'no', '0', 'false'))

    end_input = input("End game on Bingo? (y/n, default n): ").strip().lower()
    config["end_on_bingo"] = end_input in ('y', 'yes', '1', 'true')

    if mode.lower() in ("bingo", "shared_bingo", "shared-bingo", "sharedbingo"):
        free_center = input("Free center space? (y/n, default n): ").strip().lower()
        if free_center in ('y', 'yes', '1', 'true'):
            config["free_center"] = True

        lockout = input("Lockout mode? (y/n, default n): ").strip().lower()
        if lockout in ('y', 'yes', '1', 'true'):
            config["lockout"] = True

    return config


def set_gamemode(client: httpx.Client):
    mode = input("Enter gamemode (classic/shared/shared_bingo/bingo): ").strip()
    if not mode:
        print("Gamemode not changed.")
        return

    payload: Dict[str, Any] = {"mode": mode}
    if mode.lower() in ("bingo", "shared_bingo", "shared-bingo", "sharedbingo"):
        config = _prompt_bingo_config(mode)
        if config:
            payload["config"] = config

    data = _request(client, "POST", "/admin/gamemode", payload=payload)
    if not isinstance(data, dict):
        return
    print(f"Gamemode set to: {data.get('gamemode', mode)}")


def send_broadcast(client: httpx.Client):
    msg = input("Enter message: ").strip()
    if not msg:
        print("Empty message, cancelled.")
        return
    data = _request(client, "POST", "/admin/broadcast", payload={"message": msg})
    if data and data.get("status") == "ok":
        print("Broadcast sent.")


def finish_gamemode(client: httpx.Client):
    confirm = input("Finish current gamemode? (y/n): ").strip().lower()
    if confirm not in ("y", "yes", "1", "true"):
        print("Cancelled.")
        return
    data = _request(client, "POST", "/admin/gamemode/finish")
    if data and data.get("status") == "ok":
        print("Gamemode finished.")
    else:
        print("Finish failed.")


def save_cache(client: httpx.Client):
    data = _request(client, "POST", "/admin/cache/save")
    if data and data.get("status") == "ok":
        print("Cache saved to disk.")
    else:
        print("Cache save failed.")


def main():
    base_url = os.getenv("ADMIN_URL", DEFAULT_BASE_URL)
    token = os.getenv("ADMIN_TOKEN")
    print(f"Connecting to admin API at {base_url}")
    if token:
        print("Using bearer token from ADMIN_TOKEN")
    else:
        print("No ADMIN_TOKEN set; proceeding without auth header.")

    with _build_client(base_url, token) as client:
        while True:
            print("\nAdmin menu:")
            print("1) Show status")
            print("2) List users")
            print("3) Set gamemode")
            print("4) Save cache to disk")
            print("5) Broadcast news")
            print("6) Finish current gamemode")
            print("7) Quit")
            choice = input(">> ").strip().lower()

            if choice in ("1", "status"):
                show_status(client)
            elif choice in ("2", "users", "list"):
                list_users(client)
            elif choice in ("3", "mode", "gamemode"):
                set_gamemode(client)
            elif choice in ("4", "cache", "save", "savecache"):
                save_cache(client)
            elif choice in ("5", "news", "announce", "broadcast"):
                send_broadcast(client)
            elif choice in ("6", "finish", "end", "stop"):
                finish_gamemode(client)
            elif choice in ("7", "q", "quit", "exit"):
                print("Goodbye.")
                break
            else:
                print("Unknown option. Use 1-6.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(1)
