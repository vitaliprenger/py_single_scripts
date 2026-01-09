"""
Outlook 365 to Nextcloud Calendar One-Way Sync

This script fetches calendar events from Outlook 365 using Microsoft Graph API
and syncs them to a Nextcloud calendar via CalDAV.

Features:
- Token caching (no re-login on each run)
- Incremental sync (only changes are synced)
- Handles create, update, and delete operations
- Configurable sync window (past/future days)

Usage:
    python outlook_to_nextcloud_sync.py [--full-sync] [--dry-run]

Options:
    --full-sync   Force a full resync of all events
    --dry-run     Show what would be synced without making changes
"""

import argparse
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import caldav
import requests
from icalendar import Calendar, Event
from msal import PublicClientApplication, SerializableTokenCache

# Import config from helper
from helper import config

# ============================================================================
# Configuration
# ============================================================================

# Microsoft Graph API settings
MS_GRAPH_CLIENT_ID = config.ms_graph_client_id
MS_GRAPH_TENANT_ID = config.ms_graph_tenant_id
MS_GRAPH_AUTHORITY = f"https://login.microsoftonline.com/{MS_GRAPH_TENANT_ID}"
MS_GRAPH_SCOPES = ["Calendars.Read"]

# Nextcloud CalDAV settings
NEXTCLOUD_URL = config.nextcloud_url
NEXTCLOUD_USERNAME = config.nextcloud_username
NEXTCLOUD_PASSWORD = config.nextcloud_password
NEXTCLOUD_CALENDAR_NAME = config.nextcloud_calendar_name

# Sync settings
SYNC_PAST_DAYS = 30  # Sync events from X days ago
SYNC_FUTURE_DAYS = 90  # Sync events up to X days in future

# File paths for caching
SCRIPT_DIR = Path(__file__).parent
TOKEN_CACHE_FILE = SCRIPT_DIR / ".outlook_token_cache.json"
SYNC_STATE_FILE = SCRIPT_DIR / ".outlook_sync_state.json"


# ============================================================================
# Microsoft Graph API - Authentication & Event Fetching
# ============================================================================


class OutlookCalendarClient:
    """Client for fetching calendar events from Outlook 365 via Microsoft Graph API."""

    def __init__(self, client_id: str, authority: str, scopes: list[str]):
        self.scopes = scopes
        self.token_cache = SerializableTokenCache()
        self._load_token_cache()

        self.app = PublicClientApplication(
            client_id, authority=authority, token_cache=self.token_cache
        )

    def _load_token_cache(self):
        """Load token cache from file if it exists."""
        if TOKEN_CACHE_FILE.exists():
            self.token_cache.deserialize(TOKEN_CACHE_FILE.read_text())

    def _save_token_cache(self):
        """Save token cache to file."""
        if self.token_cache.has_state_changed:
            TOKEN_CACHE_FILE.write_text(self.token_cache.serialize())

    def get_access_token(self) -> str:
        """Get access token, using cached token if available."""
        # Try to get token from cache
        accounts = self.app.get_accounts()
        if accounts:
            result = self.app.acquire_token_silent(self.scopes, account=accounts[0])
            if result and "access_token" in result:
                print("✓ Using cached authentication token")
                return result["access_token"]

        # Need to authenticate interactively via device flow
        print("⚠ No cached token found, initiating device flow authentication...")
        flow = self.app.initiate_device_flow(scopes=self.scopes)

        if "user_code" not in flow:
            raise Exception(f"Failed to create device flow: {flow.get('error')}")

        print(f"\n{flow['message']}\n")

        result = self.app.acquire_token_by_device_flow(flow)
        self._save_token_cache()

        if "access_token" not in result:
            raise Exception(
                f"Token acquisition failed: {result.get('error_description')}"
            )

        print("✓ Successfully authenticated")
        return result["access_token"]

    def fetch_events(self, start_date: datetime, end_date: datetime) -> list[dict]:
        """Fetch calendar events within the specified date range."""
        access_token = self.get_access_token()
        headers = {"Authorization": f"Bearer {access_token}"}

        # Format dates for Graph API (ISO 8601)
        start_str = start_date.strftime("%Y-%m-%dT00:00:00Z")
        end_str = end_date.strftime("%Y-%m-%dT23:59:59Z")

        # Use calendarView to get expanded recurring events
        url = (
            f"https://graph.microsoft.com/v1.0/me/calendarView"
            f"?startDateTime={start_str}&endDateTime={end_str}"
            f"&$select=id,subject,start,end,location,body,isAllDay,isCancelled,"
            f"sensitivity,showAs,categories,lastModifiedDateTime"
            f"&$orderby=start/dateTime"
            f"&$top=500"
        )

        all_events = []

        while url:
            response = requests.get(url, headers=headers)

            if not response.ok:
                raise Exception(f"Error fetching events: {response.json()}")

            data = response.json()
            all_events.extend(data.get("value", []))

            # Handle pagination
            url = data.get("@odata.nextLink")

        print(f"✓ Fetched {len(all_events)} events from Outlook")
        return all_events


# ============================================================================
# Nextcloud CalDAV Client
# ============================================================================


class NextcloudCalendarClient:
    """Client for managing calendar events in Nextcloud via CalDAV."""

    def __init__(self, url: str, username: str, password: str, calendar_name: str):
        self.calendar_name = calendar_name

        # Connect to Nextcloud CalDAV
        caldav_url = f"{url}/remote.php/dav"
        self.client = caldav.DAVClient(
            url=caldav_url, username=username, password=password
        )
        self.principal = self.client.principal()
        self.calendar = self._get_or_create_calendar()

    def _get_or_create_calendar(self) -> caldav.Calendar:
        """Get the target calendar, creating it if it doesn't exist."""
        calendars = self.principal.calendars()

        for cal in calendars:
            if cal.name == self.calendar_name:
                print(f"✓ Found Nextcloud calendar: {self.calendar_name}")
                return cal

        # Calendar doesn't exist, create it
        print(f"⚠ Calendar '{self.calendar_name}' not found, creating...")
        calendar = self.principal.make_calendar(name=self.calendar_name)
        print(f"✓ Created Nextcloud calendar: {self.calendar_name}")
        return calendar

    def get_existing_events(self) -> dict[str, caldav.Event]:
        """Get all existing events in the calendar, indexed by UID."""
        events = {}
        for event in self.calendar.events():
            try:
                ical = Calendar.from_ical(event.data)
                for component in ical.walk():
                    if component.name == "VEVENT":
                        uid = str(component.get("uid", ""))
                        if uid:
                            events[uid] = event
                            break
            except Exception as e:
                print(f"⚠ Warning: Could not parse event: {e}")
        return events

    def create_event(self, ical_data: str) -> caldav.Event:
        """Create a new event in the calendar."""
        return self.calendar.save_event(ical_data)

    def update_event(self, event: caldav.Event, ical_data: str):
        """Update an existing event."""
        event.data = ical_data
        event.save()

    def delete_event(self, event: caldav.Event):
        """Delete an event from the calendar."""
        event.delete()


# ============================================================================
# Event Conversion (Outlook → iCalendar)
# ============================================================================


def outlook_event_to_ical(outlook_event: dict) -> tuple[str, str]:
    """
    Convert an Outlook event to iCalendar format.

    Returns:
        tuple: (uid, ical_string)
    """
    # Create a unique ID based on Outlook event ID
    outlook_id = outlook_event["id"]
    uid = f"outlook-{hashlib.md5(outlook_id.encode()).hexdigest()}@outlook-sync"

    cal = Calendar()
    cal.add("prodid", "-//Outlook to Nextcloud Sync//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")

    event = Event()
    event.add("uid", uid)
    event.add("summary", outlook_event.get("subject", "No Subject"))

    # Parse start and end times
    start_info = outlook_event["start"]
    end_info = outlook_event["end"]

    is_all_day = outlook_event.get("isAllDay", False)

    if is_all_day:
        # All-day events: use DATE (not DATETIME)
        start_dt = datetime.fromisoformat(start_info["dateTime"].replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end_info["dateTime"].replace("Z", "+00:00"))
        event.add("dtstart", start_dt.date())
        event.add("dtend", end_dt.date())
    else:
        # Timed events: use DATETIME with timezone
        start_dt = datetime.fromisoformat(start_info["dateTime"].replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end_info["dateTime"].replace("Z", "+00:00"))
        event.add("dtstart", start_dt)
        event.add("dtend", end_dt)

    # Location
    location = outlook_event.get("location", {})
    if isinstance(location, dict) and location.get("displayName"):
        event.add("location", location["displayName"])

    # Description (from body)
    body = outlook_event.get("body", {})
    if body.get("content"):
        # Strip HTML if content type is HTML
        content = body["content"]
        if body.get("contentType") == "html":
            # Simple HTML stripping (for proper HTML parsing, use beautifulsoup)
            import re

            content = re.sub(r"<[^>]+>", "", content)
            content = content.strip()
        if content:
            event.add("description", content)

    # Categories/tags
    categories = outlook_event.get("categories", [])
    if categories:
        event.add("categories", categories)

    # Status based on showAs
    show_as = outlook_event.get("showAs", "busy")
    status_map = {
        "free": "TRANSPARENT",
        "tentative": "TENTATIVE",
        "busy": "OPAQUE",
        "oof": "OPAQUE",
        "workingElsewhere": "OPAQUE",
    }
    event.add("transp", status_map.get(show_as, "OPAQUE"))

    # Cancelled events
    if outlook_event.get("isCancelled", False):
        event.add("status", "CANCELLED")

    # Timestamps
    event.add("dtstamp", datetime.utcnow())

    last_modified = outlook_event.get("lastModifiedDateTime")
    if last_modified:
        mod_dt = datetime.fromisoformat(last_modified.replace("Z", "+00:00"))
        event.add("last-modified", mod_dt)

    # Add custom property to track Outlook ID
    event.add("x-outlook-id", outlook_id)

    cal.add_component(event)

    return uid, cal.to_ical().decode("utf-8")


def compute_event_hash(outlook_event: dict) -> str:
    """Compute a hash of the event content to detect changes."""
    # Include fields that we care about for detecting changes
    relevant_fields = {
        "subject": outlook_event.get("subject"),
        "start": outlook_event.get("start"),
        "end": outlook_event.get("end"),
        "location": outlook_event.get("location"),
        "isAllDay": outlook_event.get("isAllDay"),
        "isCancelled": outlook_event.get("isCancelled"),
        "lastModifiedDateTime": outlook_event.get("lastModifiedDateTime"),
    }
    return hashlib.md5(json.dumps(relevant_fields, sort_keys=True).encode()).hexdigest()


# ============================================================================
# Sync State Management
# ============================================================================


class SyncState:
    """Manages the state of synced events to enable incremental sync."""

    def __init__(self, state_file: Path):
        self.state_file = state_file
        self.state = self._load()

    def _load(self) -> dict:
        """Load sync state from file."""
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text())
            except json.JSONDecodeError:
                return {"events": {}, "last_sync": None}
        return {"events": {}, "last_sync": None}

    def save(self):
        """Save sync state to file."""
        self.state["last_sync"] = datetime.utcnow().isoformat()
        self.state_file.write_text(json.dumps(self.state, indent=2))

    def get_synced_event(self, outlook_id: str) -> Optional[dict]:
        """Get info about a previously synced event."""
        return self.state["events"].get(outlook_id)

    def mark_synced(self, outlook_id: str, uid: str, content_hash: str):
        """Mark an event as synced."""
        self.state["events"][outlook_id] = {
            "uid": uid,
            "hash": content_hash,
            "synced_at": datetime.utcnow().isoformat(),
        }

    def remove_event(self, outlook_id: str):
        """Remove an event from sync state."""
        self.state["events"].pop(outlook_id, None)

    def get_all_synced_outlook_ids(self) -> set[str]:
        """Get all Outlook event IDs that have been synced."""
        return set(self.state["events"].keys())

    def clear(self):
        """Clear all sync state for full resync."""
        self.state = {"events": {}, "last_sync": None}


# ============================================================================
# Main Sync Logic
# ============================================================================


def sync_calendars(dry_run: bool = False, full_sync: bool = False):
    """
    Perform one-way sync from Outlook 365 to Nextcloud.

    Args:
        dry_run: If True, show what would be synced without making changes
        full_sync: If True, clear sync state and resync everything
    """
    print("=" * 60)
    print("Outlook 365 → Nextcloud Calendar Sync")
    print("=" * 60)

    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")

    # Initialize clients
    print("\n📅 Connecting to Outlook 365...")
    outlook = OutlookCalendarClient(
        MS_GRAPH_CLIENT_ID, MS_GRAPH_AUTHORITY, MS_GRAPH_SCOPES
    )

    print("\n☁️  Connecting to Nextcloud...")
    nextcloud = NextcloudCalendarClient(
        NEXTCLOUD_URL, NEXTCLOUD_USERNAME, NEXTCLOUD_PASSWORD, NEXTCLOUD_CALENDAR_NAME
    )

    # Load sync state
    sync_state = SyncState(SYNC_STATE_FILE)
    if full_sync:
        print("\n⚠️  Full sync requested - clearing sync state")
        sync_state.clear()

    # Calculate date range
    now = datetime.utcnow()
    start_date = now - timedelta(days=SYNC_PAST_DAYS)
    end_date = now + timedelta(days=SYNC_FUTURE_DAYS)

    print(f"\n📆 Sync window: {start_date.date()} to {end_date.date()}")

    # Fetch events from Outlook
    print("\n📥 Fetching events from Outlook...")
    outlook_events = outlook.fetch_events(start_date, end_date)

    # Build lookup of current Outlook events
    outlook_event_ids = set()

    # Get existing Nextcloud events
    print("\n📋 Checking existing Nextcloud events...")
    nextcloud_events = nextcloud.get_existing_events()
    print(f"✓ Found {len(nextcloud_events)} existing events in Nextcloud")

    # Track stats
    stats = {"created": 0, "updated": 0, "deleted": 0, "unchanged": 0}

    # Process Outlook events
    print("\n🔄 Processing events...")

    for outlook_event in outlook_events:
        outlook_id = outlook_event["id"]
        outlook_event_ids.add(outlook_id)

        # Skip cancelled events
        if outlook_event.get("isCancelled", False):
            continue

        # Convert to iCal
        uid, ical_data = outlook_event_to_ical(outlook_event)
        content_hash = compute_event_hash(outlook_event)

        # Check if we've synced this event before
        synced_info = sync_state.get_synced_event(outlook_id)

        if synced_info:
            # Event was previously synced
            if synced_info["hash"] == content_hash:
                # No changes
                stats["unchanged"] += 1
                continue
            else:
                # Event was modified
                subject = outlook_event.get("subject", "No Subject")
                print(f"  📝 Updating: {subject}")

                if not dry_run:
                    existing_uid = synced_info["uid"]
                    if existing_uid in nextcloud_events:
                        nextcloud.update_event(
                            nextcloud_events[existing_uid], ical_data
                        )
                    else:
                        # Event was deleted from Nextcloud, recreate it
                        nextcloud.create_event(ical_data)
                    sync_state.mark_synced(outlook_id, uid, content_hash)

                stats["updated"] += 1
        else:
            # New event
            subject = outlook_event.get("subject", "No Subject")
            start = outlook_event.get("start", {}).get("dateTime", "Unknown time")
            print(f"  ➕ Creating: {subject} ({start[:10]})")

            if not dry_run:
                nextcloud.create_event(ical_data)
                sync_state.mark_synced(outlook_id, uid, content_hash)

            stats["created"] += 1

    # Handle deleted events (events that were synced but no longer exist in Outlook)
    synced_outlook_ids = sync_state.get_all_synced_outlook_ids()
    deleted_ids = synced_outlook_ids - outlook_event_ids

    for deleted_outlook_id in deleted_ids:
        synced_info = sync_state.get_synced_event(deleted_outlook_id)
        if synced_info:
            uid = synced_info["uid"]
            print(f"  🗑️  Deleting event (removed from Outlook): {uid}")

            if not dry_run:
                if uid in nextcloud_events:
                    nextcloud.delete_event(nextcloud_events[uid])
                sync_state.remove_event(deleted_outlook_id)

            stats["deleted"] += 1

    # Save sync state
    if not dry_run:
        sync_state.save()

    # Print summary
    print("\n" + "=" * 60)
    print("📊 Sync Summary")
    print("=" * 60)
    print(f"  ➕ Created:   {stats['created']}")
    print(f"  📝 Updated:   {stats['updated']}")
    print(f"  🗑️  Deleted:   {stats['deleted']}")
    print(f"  ⏸️  Unchanged: {stats['unchanged']}")
    print("=" * 60)

    if dry_run:
        print("\n🔍 This was a DRY RUN - no changes were made")
    else:
        print("\n✅ Sync completed successfully!")


# ============================================================================
# CLI Entry Point
# ============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="One-way sync from Outlook 365 to Nextcloud calendar"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be synced without making changes",
    )
    parser.add_argument(
        "--full-sync",
        action="store_true",
        help="Clear sync state and perform a full resync",
    )

    args = parser.parse_args()

    try:
        sync_calendars(dry_run=args.dry_run, full_sync=args.full_sync)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise


if __name__ == "__main__":
    main()
