#!/usr/bin/env python3
"""Backfill Cursor's composerHeaders SQL table from cursaves ItemTable index.

cursaves 0.9.1 writes imported chats to ItemTable key composer.composerHeaders.
Newer Cursor builds list chats from the dedicated composerHeaders table instead,
so imports are invisible until those rows exist.

Requires Cursor to be fully quit (no /usr/share/cursor/cursor processes).
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

GLOBAL_DB = Path.home() / ".config/Cursor/User/globalStorage/state.vscdb"
WS_ROOT = Path.home() / ".config/Cursor/User/workspaceStorage"


def cursor_running() -> bool:
    try:
        out = subprocess.check_output(["pgrep", "-f", r"/usr/share/cursor/cursor"], text=True)
    except subprocess.CalledProcessError:
        return False
    pids = [p for p in out.split() if p.isdigit()]
    return bool(pids)


def backup_db(db: Path) -> Path:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    dest = db.with_name(f"state.backup_headers_{stamp}.vscdb")
    shutil.copy2(db, dest)
    for suffix in ("-wal", "-shm"):
        side = Path(str(db) + suffix)
        if side.exists():
            shutil.copy2(side, Path(str(dest) + suffix))
    return dest


def ensure_selected(ws_id: str, composer_id: str) -> None:
    ws_db = WS_ROOT / ws_id / "state.vscdb"
    if not ws_db.exists():
        print(f"  skip selectedComposerIds: missing workspace DB {ws_id}")
        return
    con = sqlite3.connect(ws_db)
    try:
        row = con.execute(
            "SELECT value FROM ItemTable WHERE key='composer.composerData'"
        ).fetchone()
        data = json.loads(row[0]) if row else {"selectedComposerIds": []}
        selected = data.get("selectedComposerIds") or []
        if composer_id not in selected:
            selected.append(composer_id)
            data["selectedComposerIds"] = selected
            data.setdefault("hasMigratedComposerData", True)
            data.setdefault("hasMigratedMultipleComposers", True)
            payload = json.dumps(data, separators=(",", ":"))
            if row:
                con.execute(
                    "UPDATE ItemTable SET value=? WHERE key='composer.composerData'",
                    (payload,),
                )
            else:
                con.execute(
                    "INSERT INTO ItemTable (key, value) VALUES ('composer.composerData', ?)",
                    (payload,),
                )
            con.commit()
            print(f"  + selectedComposerIds in {ws_id[:8]}…")
    finally:
        con.close()


def main() -> int:
    if cursor_running():
        print(
            "ERROR: Cursor is still running.\n"
            "Fully quit Cursor (File → Exit / right-click tray → Quit), then re-run:\n"
            f"  python3 {Path(__file__).resolve()}",
            file=sys.stderr,
        )
        return 1

    if not GLOBAL_DB.exists():
        print(f"ERROR: missing {GLOBAL_DB}", file=sys.stderr)
        return 1

    bak = backup_db(GLOBAL_DB)
    print(f"Backup: {bak}")

    con = sqlite3.connect(GLOBAL_DB)
    try:
        row = con.execute(
            "SELECT value FROM ItemTable WHERE key='composer.composerHeaders'"
        ).fetchone()
        if not row:
            print("ERROR: ItemTable composer.composerHeaders missing", file=sys.stderr)
            return 1

        headers = json.loads(row[0])
        all_composers = headers.get("allComposers") or []
        existing = {
            r[0] for r in con.execute("SELECT composerId FROM composerHeaders")
        }

        inserted = 0
        for entry in all_composers:
            cid = entry.get("composerId")
            if not cid or cid in existing:
                continue

            wi = entry.get("workspaceIdentifier") or {}
            ws_id = wi.get("id")
            if not ws_id:
                print(f"  skip {cid}: no workspaceIdentifier.id")
                continue

            created = int(entry.get("createdAt") or 0)
            updated = int(entry.get("lastUpdatedAt") or created or 0)
            # Enrich value to match native Cursor header shape
            value = dict(entry)
            value.setdefault("type", "head")
            value.setdefault("hasBlockingPendingActions", False)
            value.setdefault("hasPendingPlan", False)
            value.setdefault("isProject", False)
            value.setdefault("worktreeStartedReadOnly", False)
            value.setdefault("trackedGitRepos", [])
            if "conversationCheckpointLastUpdatedAt" not in value:
                value["conversationCheckpointLastUpdatedAt"] = updated

            con.execute(
                """
                INSERT INTO composerHeaders (
                    composerId, workspaceId, createdAt, lastUpdatedAt,
                    isArchived, isSubagent, recency, checkpointAt, value
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cid,
                    ws_id,
                    created,
                    updated,
                    1 if value.get("isArchived") else 0,
                    0,
                    updated,
                    updated,
                    json.dumps(value, separators=(",", ":")),
                ),
            )
            ensure_selected(ws_id, cid)
            print(f"  + {cid[:8]}  {value.get('name')}  → {ws_id[:8]}…")
            inserted += 1
            existing.add(cid)

        con.commit()
        # checkpoint WAL into main db
        con.execute("PRAGMA wal_checkpoint(FULL)")
        print(f"\nDone: inserted {inserted} composerHeaders row(s).")
        print("Reopen Cursor and check Agents history for each project folder.")
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
