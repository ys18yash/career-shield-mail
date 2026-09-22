import os
import json
import sqlite3
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

DB_PATH = os.environ.get("CAREERSHIELD_DB_PATH", os.environ.get("CYBERSHIELD_DB_PATH", "data/careershield_store.db" if os.path.exists("data/careershield_store.db") else ("data/cybershield_store.db" if os.path.exists("data/cybershield_store.db") else "data/careershield_store.db")))

def init_db(db_path: str = DB_PATH):
    """Initializes SQLite database schema for persistent threat logging and email metadata."""
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scan_records (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                sender TEXT,
                subject TEXT,
                model_used TEXT NOT NULL,
                risk_score REAL NOT NULL,
                is_spam INTEGER NOT NULL,
                threat_level TEXT NOT NULL,
                security_triggers_json TEXT,
                body_snippet TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS quarantine_records (
                id TEXT PRIMARY KEY,
                quarantine_time TEXT NOT NULL,
                sender TEXT,
                subject TEXT,
                risk_score REAL NOT NULL,
                threat_level TEXT NOT NULL,
                status TEXT DEFAULT 'quarantined'
            )
        ''')
        conn.commit()

class StorageManager:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        init_db(self.db_path)

    def log_scan(self, scan_id: str, sender: str, subject: str, model_used: str,
                 risk_score: float, is_spam: bool, threat_level: str,
                 security_triggers: List[Dict[str, Any]], body_snippet: str) -> None:
        """Persists a scan event safely."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO scan_records
                    (id, timestamp, sender, subject, model_used, risk_score, is_spam, threat_level, security_triggers_json, body_snippet)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    scan_id,
                    datetime.utcnow().isoformat(),
                    sender,
                    subject,
                    model_used,
                    risk_score,
                    1 if is_spam else 0,
                    threat_level,
                    json.dumps(security_triggers),
                    body_snippet[:500]
                ))
                if is_spam:
                    cursor.execute('''
                        INSERT OR REPLACE INTO quarantine_records
                        (id, quarantine_time, sender, subject, risk_score, threat_level, status)
                        VALUES (?, ?, ?, ?, ?, ?, 'quarantined')
                    ''', (
                        scan_id,
                        datetime.utcnow().isoformat(),
                        sender,
                        subject,
                        risk_score,
                        threat_level
                    ))
                conn.commit()
        except Exception as e:
            pass

    def get_recent_scans(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieves recent scan records."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM scan_records ORDER BY timestamp DESC LIMIT ?
                ''', (limit,))
                rows = cursor.fetchall()
                results = []
                for r in rows:
                    item = dict(r)
                    item["is_spam"] = bool(item["is_spam"])
                    try:
                        item["security_triggers"] = json.loads(item["security_triggers_json"])
                    except:
                        item["security_triggers"] = []
                    results.append(item)
                return results
        except Exception:
            return []

    def get_quarantine_items(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves active quarantined emails."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM quarantine_records WHERE status = 'quarantined' ORDER BY quarantine_time DESC LIMIT ?
                ''', (limit,))
                return [dict(r) for r in cursor.fetchall()]
        except Exception:
            return []

storage = StorageManager()
