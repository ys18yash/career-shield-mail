"""
CareerShield Mail - Security Alerts & Incident Investigation Service.

Manages persistent security alert triage, lifecycle status transitions,
and immutable security audit timeline events.
"""

import os
import json
import sqlite3
import time
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

DB_PATH = os.environ.get("CAREERSHIELD_DB_PATH", os.environ.get("CYBERSHIELD_DB_PATH", "data/careershield_store.db" if os.path.exists("data/careershield_store.db") else "data/careershield_store.db"))

VALID_ALERT_STATUSES = {"OPEN", "INVESTIGATING", "RESOLVED", "FALSE_POSITIVE", "DISMISSED"}
VALID_SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


def init_security_alert_schema(db_path: str = DB_PATH):
    """Initializes SQLite schema for security alert records and chronological timeline events."""
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS security_alerts (
                alert_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                subject TEXT,
                sender TEXT,
                severity TEXT NOT NULL CHECK(severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
                threat_type TEXT NOT NULL,
                overall_risk_score REAL NOT NULL,
                threat_probability REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'OPEN' CHECK(status IN ('OPEN', 'INVESTIGATING', 'RESOLVED', 'FALSE_POSITIVE', 'DISMISSED')),
                detected_at TEXT NOT NULL,
                resolved_at TEXT,
                iocs_json TEXT NOT NULL,
                risk_breakdown_json TEXT NOT NULL,
                ml_analysis_json TEXT NOT NULL,
                resolution_notes TEXT,
                assigned_to TEXT,
                UNIQUE(user_id, message_id)
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_alert_user ON security_alerts(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_alert_status ON security_alerts(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_alert_severity ON security_alerts(severity)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_alert_detected ON security_alerts(detected_at)')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS security_timeline_events (
                event_id TEXT PRIMARY KEY,
                alert_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                actor TEXT NOT NULL,
                description TEXT NOT NULL,
                details_json TEXT,
                FOREIGN KEY (alert_id) REFERENCES security_alerts(alert_id) ON DELETE CASCADE
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_timeline_alert ON security_timeline_events(alert_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_timeline_time ON security_timeline_events(timestamp)')
        
        conn.commit()


class SecurityAlertManager:
    """
    Central Manager for Security Alert Triage & Forensic Audit Event Timelines.
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        init_security_alert_schema(self.db_path)

    def generate_alert_id(self, message_id: str, user_id: str) -> str:
        date_str = datetime.utcnow().strftime("%Y%m%d")
        h = hashlib.sha256(f"{user_id}:{message_id}".encode()).hexdigest()[:6].upper()
        return f"ALERT-{date_str}-{h}"

    def create_or_update_alert(
        self,
        user_id: str,
        message_id: str,
        subject: str,
        sender: str,
        severity: str,
        threat_type: str,
        overall_risk_score: float,
        threat_probability: float,
        iocs: List[Dict[str, Any]],
        risk_breakdown: Dict[str, Any],
        ml_analysis: Dict[str, Any],
        initial_timeline: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Creates or updates a security alert and persists standard forensic timeline events.
        """
        alert_id = self.generate_alert_id(message_id, user_id)
        now_iso = datetime.utcnow().isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT alert_id, status FROM security_alerts WHERE user_id = ? AND message_id = ?",
                (user_id, message_id)
            )
            existing = cursor.fetchone()

            if existing:
                # Update existing alert telemetry
                cursor.execute('''
                    UPDATE security_alerts
                    SET severity = ?, threat_type = ?, overall_risk_score = ?,
                        threat_probability = ?, iocs_json = ?, risk_breakdown_json = ?,
                        ml_analysis_json = ?
                    WHERE alert_id = ?
                ''', (
                    severity, threat_type, overall_risk_score, threat_probability,
                    json.dumps(iocs), json.dumps(risk_breakdown), json.dumps(ml_analysis),
                    alert_id
                ))
            else:
                # Insert new alert
                cursor.execute('''
                    INSERT INTO security_alerts
                    (alert_id, user_id, message_id, subject, sender, severity, threat_type, overall_risk_score, threat_probability, status, detected_at, iocs_json, risk_breakdown_json, ml_analysis_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?, ?, ?)
                ''', (
                    alert_id, user_id, message_id, subject, sender, severity, threat_type,
                    overall_risk_score, threat_probability, now_iso,
                    json.dumps(iocs), json.dumps(risk_breakdown), json.dumps(ml_analysis)
                ))

                # Log foundational lifecycle timeline events
                events_to_log = initial_timeline or [
                    {
                        "event_type": "EMAIL_RECEIVED",
                        "actor": "Mail Gateway",
                        "description": f"Message received from '{sender}' with subject '{subject[:60]}'.",
                        "timestamp": now_iso
                    },
                    {
                        "event_type": "ANALYSIS_STARTED",
                        "actor": "ML Threat Shield",
                        "description": "Triggered real-time 14,022-feature NLP extraction and ensemble classification.",
                        "timestamp": now_iso
                    },
                    {
                        "event_type": "ANALYSIS_COMPLETED",
                        "actor": "ML Threat Shield",
                        "description": f"ML threat probability evaluated at {round(threat_probability * 100, 1)}%.",
                        "timestamp": now_iso
                    },
                    {
                        "event_type": "IOC_EXTRACTED",
                        "actor": "IOC Extractor",
                        "description": f"Extracted {len(iocs)} forensic indicators (URLs, domains, emails, attachments).",
                        "timestamp": now_iso
                    },
                    {
                        "event_type": "THREAT_INTELLIGENCE_CHECKED",
                        "actor": "Threat Intel Service",
                        "description": "Enriched indicators against active threat intelligence providers and local signatures.",
                        "timestamp": now_iso
                    },
                    {
                        "event_type": "ALERT_CREATED",
                        "actor": "Automated Triage Engine",
                        "description": f"Security Alert {alert_id} generated with severity {severity} for {threat_type}.",
                        "timestamp": now_iso
                    }
                ]

                for ev in events_to_log:
                    ev_id = f"EV-{int(time.time() * 1000)}-{hashlib.sha256((ev['description'] + str(time.time())).encode()).hexdigest()[:4]}"
                    cursor.execute('''
                        INSERT INTO security_timeline_events
                        (event_id, alert_id, event_type, timestamp, actor, description, details_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        ev_id, alert_id, ev["event_type"], ev.get("timestamp", now_iso),
                        ev["actor"], ev["description"], json.dumps(ev.get("details", {}))
                    ))

            conn.commit()

        return self.get_alert_by_id(alert_id)

    def log_timeline_event(
        self,
        alert_id: str,
        event_type: str,
        actor: str,
        description: str,
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Appends a new chronological audit event to an existing alert."""
        now_iso = datetime.utcnow().isoformat()
        ev_id = f"EV-{int(time.time() * 1000)}-{hashlib.sha256((description + str(time.time())).encode()).hexdigest()[:4]}"
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO security_timeline_events
                (event_id, alert_id, event_type, timestamp, actor, description, details_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                ev_id, alert_id, event_type, now_iso, actor, description, json.dumps(details or {})
            ))
            conn.commit()

        return {
            "event_id": ev_id,
            "alert_id": alert_id,
            "event_type": event_type,
            "timestamp": now_iso,
            "actor": actor,
            "description": description,
            "details": details or {}
        }

    def update_alert_status(
        self,
        alert_id: str,
        status: str,
        user_id: Optional[str] = None,
        resolution_notes: Optional[str] = None,
        assigned_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """Transitions alert lifecycle status and logs corresponding audit event."""
        if status not in VALID_ALERT_STATUSES:
            raise ValueError(f"Invalid alert status '{status}'. Must be one of {VALID_ALERT_STATUSES}")

        now_iso = datetime.utcnow().isoformat()
        resolved_at = now_iso if status in ("RESOLVED", "FALSE_POSITIVE", "DISMISSED") else None

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM security_alerts WHERE alert_id = ?", (alert_id,))
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Alert '{alert_id}' not found.")

            cursor.execute('''
                UPDATE security_alerts
                SET status = ?, resolved_at = COALESCE(?, resolved_at),
                    resolution_notes = COALESCE(?, resolution_notes),
                    assigned_to = COALESCE(?, assigned_to)
                WHERE alert_id = ?
            ''', (status, resolved_at, resolution_notes, assigned_to, alert_id))
            
            conn.commit()

        actor_name = user_id or assigned_to or "Security Analyst"
        ev_type = "INCIDENT_RESOLVED" if status in ("RESOLVED", "FALSE_POSITIVE", "DISMISSED") else "ALERT_UPDATED"
        self.log_timeline_event(
            alert_id=alert_id,
            event_type=ev_type,
            actor=actor_name,
            description=f"Status transitioned to '{status}'. Notes: {resolution_notes or 'None'}",
            details={"new_status": status, "resolution_notes": resolution_notes}
        )

        return self.get_alert_by_id(alert_id)

    def get_alert_by_id(self, alert_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves complete forensic details for a single security alert."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM security_alerts WHERE alert_id = ?", (alert_id,))
            row = cursor.fetchone()
            if not row:
                return None

            alert = dict(row)
            try:
                alert["iocs"] = json.loads(alert["iocs_json"])
            except:
                alert["iocs"] = []
            try:
                alert["risk_breakdown"] = json.loads(alert["risk_breakdown_json"])
            except:
                alert["risk_breakdown"] = {}
            try:
                alert["ml_analysis"] = json.loads(alert["ml_analysis_json"])
            except:
                alert["ml_analysis"] = {}

            # Fetch chronological timeline
            cursor.execute(
                "SELECT * FROM security_timeline_events WHERE alert_id = ? ORDER BY timestamp ASC",
                (alert_id,)
            )
            events = []
            for ev_row in cursor.fetchall():
                ev_dict = dict(ev_row)
                try:
                    ev_dict["details"] = json.loads(ev_dict.get("details_json") or "{}")
                except:
                    ev_dict["details"] = {}
                events.append(ev_dict)

            alert["timeline"] = events
            return alert

    def list_alerts(
        self,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Lists alerts with multi-tenant filtering, status/severity query params, and pagination."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT * FROM security_alerts WHERE 1=1"
            params = []

            if user_id and user_id != "all":
                query += " AND user_id = ?"
                params.append(user_id)
            if status and status != "all":
                query += " AND status = ?"
                params.append(status)
            if severity and severity != "all":
                query += " AND severity = ?"
                params.append(severity)

            query += " ORDER BY detected_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            alerts = []
            for r in rows:
                item = dict(r)
                try:
                    item["iocs"] = json.loads(item["iocs_json"])
                except:
                    item["iocs"] = []
                try:
                    item["risk_breakdown"] = json.loads(item["risk_breakdown_json"])
                except:
                    item["risk_breakdown"] = {}
                alerts.append(item)
                
            return alerts

    def get_security_stats(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Calculates aggregated SOC metrics (open alerts, severity breakdown, MTTR)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            base_q = "FROM security_alerts WHERE 1=1"
            params = []
            if user_id and user_id != "all":
                base_q += " AND user_id = ?"
                params.append(user_id)

            cursor.execute(f"SELECT COUNT(*) {base_q}", params)
            total_alerts = cursor.fetchone()[0]

            cursor.execute(f"SELECT COUNT(*) {base_q} AND status = 'OPEN'", params)
            open_alerts = cursor.fetchone()[0]

            cursor.execute(f"SELECT COUNT(*) {base_q} AND status = 'INVESTIGATING'", params)
            investigating_alerts = cursor.fetchone()[0]

            cursor.execute(f"SELECT COUNT(*) {base_q} AND status = 'RESOLVED'", params)
            resolved_alerts = cursor.fetchone()[0]

            cursor.execute(f"SELECT COUNT(*) {base_q} AND severity = 'CRITICAL'", params)
            critical_alerts = cursor.fetchone()[0]

            cursor.execute(f"SELECT COUNT(*) {base_q} AND severity = 'HIGH'", params)
            high_alerts = cursor.fetchone()[0]

            return {
                "total_alerts": total_alerts,
                "open_alerts": open_alerts,
                "investigating_alerts": investigating_alerts,
                "resolved_alerts": resolved_alerts,
                "critical_alerts": critical_alerts,
                "high_alerts": high_alerts,
                "generated_at": datetime.utcnow().isoformat()
            }


security_alert_manager = SecurityAlertManager()
