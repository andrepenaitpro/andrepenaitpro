from __future__ import annotations

import csv
import os
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable, List

import feedparser
import requests
import smtplib
import yaml
from dateutil import parser as date_parser
from dotenv import load_dotenv


@dataclass
class Listing:
    source: str
    area: str
    title: str
    url: str
    posted_at: str
    fetched_at: str


class ListingStore:
    def __init__(self, db_path: str) -> None:
        self.conn = sqlite3.connect(db_path)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS listings (
                url TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                area TEXT NOT NULL,
                title TEXT NOT NULL,
                posted_at TEXT,
                fetched_at TEXT NOT NULL
            )
            """
        )
        self.conn.commit()

    def insert_if_new(self, listing: Listing) -> bool:
        try:
            self.conn.execute(
                "INSERT INTO listings(url, source, area, title, posted_at, fetched_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    listing.url,
                    listing.source,
                    listing.area,
                    listing.title,
                    listing.posted_at,
                    listing.fetched_at,
                ),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def export_csv(self, path: str) -> None:
        rows = self.conn.execute(
            "SELECT source, area, title, url, posted_at, fetched_at FROM listings ORDER BY fetched_at DESC"
        ).fetchall()
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["source", "area", "title", "url", "posted_at", "fetched_at"])
            writer.writerows(rows)


class Notifier:
    def __init__(self, email_enabled: bool, sms_enabled: bool) -> None:
        self.email_enabled = email_enabled
        self.sms_enabled = sms_enabled

    def notify(self, listings: List[Listing]) -> None:
        if not listings:
            return
        text = "\n".join(
            f"[{item.source}/{item.area}] {item.title}\n{item.url}" for item in listings
        )
        if self.email_enabled:
            self._send_email(text)
        if self.sms_enabled:
            self._send_sms(text)

    def _send_email(self, text: str) -> None:
        host = os.getenv("SMTP_HOST")
        port = int(os.getenv("SMTP_PORT", "587"))
        user = os.getenv("SMTP_USER")
        password = os.getenv("SMTP_PASS")
        to_addr = os.getenv("ALERT_EMAIL_TO")
        from_addr = os.getenv("ALERT_EMAIL_FROM", user)
        if not all([host, user, password, to_addr, from_addr]):
            print("Email enabled but SMTP environment variables are incomplete.")
            return

        msg = EmailMessage()
        msg["Subject"] = "New side-work listings found"
        msg["From"] = from_addr
        msg["To"] = to_addr
        msg.set_content(text)

        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg)

    def _send_sms(self, text: str) -> None:
        sid = os.getenv("TWILIO_ACCOUNT_SID")
        token = os.getenv("TWILIO_AUTH_TOKEN")
        from_number = os.getenv("TWILIO_FROM_NUMBER")
        to_number = os.getenv("ALERT_SMS_TO")
        if not all([sid, token, from_number, to_number]):
            print("SMS enabled but Twilio environment variables are incomplete.")
            return

        requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            auth=(sid, token),
            data={"From": from_number, "To": to_number, "Body": text[:1500]},
            timeout=30,
        ).raise_for_status()


def normalize_datetime(value: str | None) -> str:
    if not value:
        return ""
    try:
        dt = date_parser.parse(value)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return value


def fetch_craigslist(area: str, keywords: Iterable[str]) -> List[Listing]:
    keyword_query = "%20".join(k.strip() for k in keywords if k.strip())
    url = f"https://{area}.craigslist.org/search/jjj?format=rss&query={keyword_query}"
    feed = feedparser.parse(url)
    now = datetime.now(timezone.utc).isoformat()
    out: List[Listing] = []

    for entry in feed.entries:
        out.append(
            Listing(
                source="craigslist",
                area=area,
                title=entry.get("title", "(no title)"),
                url=entry.get("link", ""),
                posted_at=normalize_datetime(entry.get("published")),
                fetched_at=now,
            )
        )
    return out


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def main() -> None:
    load_dotenv()
    config_path = os.getenv("APP_CONFIG", "config.yaml")
    if not Path(config_path).exists():
        raise FileNotFoundError(
            f"Config file '{config_path}' not found. Copy config.example.yaml to config.yaml first."
        )

    config = load_config(config_path)
    keywords = config["search"]["keywords"]
    store = ListingStore(config["database_path"])
    notifier = Notifier(
        email_enabled=bool(config["notifications"].get("email", False)),
        sms_enabled=bool(config["notifications"].get("sms", False)),
    )

    interval = int(config.get("poll_interval_seconds", 60))
    craigslist = config["search"]["craigslist"]

    if config["search"].get("nextdoor", {}).get("enabled"):
        print("Nextdoor connector disabled in this starter. Use official exports/API only.")
    if config["search"].get("facebook", {}).get("enabled"):
        print("Facebook connector disabled in this starter. Use official exports/API only.")

    while True:
        new_items: List[Listing] = []
        if craigslist.get("enabled", False):
            for area in craigslist.get("areas", []):
                for listing in fetch_craigslist(area, keywords):
                    if listing.url and store.insert_if_new(listing):
                        new_items.append(listing)

        store.export_csv(config["output_csv"])
        if new_items:
            print(f"Found {len(new_items)} new listings.")
            notifier.notify(new_items)
        else:
            print("No new listings.")

        time.sleep(interval)


if __name__ == "__main__":
    main()
