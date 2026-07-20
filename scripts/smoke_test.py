"""End-to-end smoke test against a running telesoft backend.

Standalone async script (NOT part of src/telesoft/, NOT part of the pytest
suite). Exercises the public HTTP API: login, list/create/get/delete channel,
and verifies each step with [OK]/[FAIL] output via print (no loguru dependency).

Does NOT exercise the replace-link flow (that requires real Telegram post
URLs and a connected bot — out of scope for a smoke test).

Usage:
    cd /root/workspace/telesoft && uv run python scripts/smoke_test.py

Environment:
    TELESOFT_API_URL      backend base URL (default http://localhost:8000)
    TELESOFT_ADMIN_USER   admin username (default admin)
    TELESOFT_ADMIN_PASS   admin password (default changeme)

Exit codes:
    0 — all steps passed
    1 — at least one step failed
"""

from __future__ import annotations

import asyncio
import os
import sys

import httpx

DEFAULT_URL = "http://localhost:8000"
TEST_TELEGRAM_ID = -1003903711726
TEST_TITLE = "Smoke Test"


def _print_ok(label: str) -> None:
    print(f"[OK]   {label}")


def _print_fail(label: str, detail: str) -> None:
    print(f"[FAIL] {label} — {detail}")


async def _login(client: httpx.AsyncClient, username: str, password: str) -> bool:
    label = "POST /api/auth/login"
    try:
        resp = await client.post(
            "/api/auth/login",
            json={"username": username, "password": password},
        )
    except httpx.HTTPError as exc:
        _print_fail(label, f"network error: {exc}")
        return False
    if resp.status_code != 200:
        _print_fail(label, f"status={resp.status_code} body={resp.text}")
        return False
    _print_ok(label)
    return True


async def _list_channels(client: httpx.AsyncClient) -> bool:
    label = "GET /api/channels"
    try:
        resp = await client.get("/api/channels")
    except httpx.HTTPError as exc:
        _print_fail(label, f"network error: {exc}")
        return False
    if resp.status_code != 200:
        _print_fail(label, f"status={resp.status_code} body={resp.text}")
        return False
    data = resp.json()
    if "channels" not in data or "total" not in data:
        _print_fail(label, f"unexpected body: {data}")
        return False
    _print_ok(f"{label} (total={data['total']})")
    return True


async def _create_channel(client: httpx.AsyncClient) -> int | None:
    label = "POST /api/channels"
    try:
        resp = await client.post(
            "/api/channels",
            json={
                "telegram_id": TEST_TELEGRAM_ID,
                "title": TEST_TITLE,
                "username": None,
            },
        )
    except httpx.HTTPError as exc:
        _print_fail(label, f"network error: {exc}")
        return None
    if resp.status_code == 409:
        _print_fail(label, "channel with this telegram_id already exists")
        return None
    if resp.status_code != 201:
        _print_fail(label, f"status={resp.status_code} body={resp.text}")
        return None
    body = resp.json()
    channel_id = body.get("id")
    if channel_id is None:
        _print_fail(label, f"no id in body: {body}")
        return None
    _print_ok(f"{label} (id={channel_id})")
    return int(channel_id)


async def _get_channel(client: httpx.AsyncClient, channel_id: int) -> bool:
    label = f"GET /api/channels/{channel_id}"
    try:
        resp = await client.get(f"/api/channels/{channel_id}")
    except httpx.HTTPError as exc:
        _print_fail(label, f"network error: {exc}")
        return False
    if resp.status_code != 200:
        _print_fail(label, f"status={resp.status_code} body={resp.text}")
        return False
    body = resp.json()
    if int(body.get("telegram_id", 0)) != TEST_TELEGRAM_ID:
        _print_fail(label, f"telegram_id mismatch: {body}")
        return False
    _print_ok(label)
    return True


async def _delete_channel(client: httpx.AsyncClient, channel_id: int) -> bool:
    label = f"DELETE /api/channels/{channel_id}"
    try:
        resp = await client.delete(f"/api/channels/{channel_id}")
    except httpx.HTTPError as exc:
        _print_fail(label, f"network error: {exc}")
        return False
    if resp.status_code != 204:
        _print_fail(label, f"status={resp.status_code} body={resp.text}")
        return False
    _print_ok(label)
    return True


async def main() -> int:
    base_url = os.environ.get("TELESOFT_API_URL", DEFAULT_URL).rstrip("/")
    username = os.environ.get("TELESOFT_ADMIN_USER", "admin")
    password = os.environ.get("TELESOFT_ADMIN_PASS", "changeme")
    print(f"smoke test against {base_url} (user={username})")
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        steps: list[bool] = []
        steps.append(await _login(client, username, password))
        steps.append(await _list_channels(client))
        channel_id = await _create_channel(client)
        if channel_id is None:
            steps.append(False)
        else:
            steps.append(await _get_channel(client, channel_id))
            steps.append(await _delete_channel(client, channel_id))
    failed = [i for i, ok in enumerate(steps, start=1) if not ok]
    if failed:
        print(f"\nsmoke test FAILED: {len(failed)}/{len(steps)} step(s) failed")
        return 1
    print(f"\nsmoke test OK: {len(steps)}/{len(steps)} step(s) passed")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
