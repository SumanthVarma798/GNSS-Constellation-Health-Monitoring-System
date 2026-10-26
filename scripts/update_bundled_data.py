#!/usr/bin/env python3
"""
Update Bundled Data Script
Run this script locally to fetch fresh TLE and GP history data 
and save it to the data/ directory for bundled deployment.

Usage:
    python scripts/update_bundled_data.py --username YOUR_USERNAME --password YOUR_PASSWORD
    
Or set environment variables:
    SPACETRACK_USERNAME=your_username
    SPACETRACK_PASSWORD=your_password
    python scripts/update_bundled_data.py

Or keep them in the git-ignored .env (see .env.example) and load it first:
    set -a; . ./.env; set +a

GPS, GLONASS and Galileo are fetched only when named (--constellation gps, glonass or galileo), never
by "all": about 30 satellites each, a year apiece, is a large request to Space-Track and a large file in data/.

Or the script will automatically read from .streamlit/secrets.toml if available.
"""

import argparse
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.config import BEIDOU3_SATS, MEO_SATS, NAVIK_SATS, QZSS_SATS
from api.celestrak_api import fetch_tles_from_celestrak
from data.tle_cache import (
    load_bundled_gp_history,
    save_gp_history_to_bundle,
    save_tles_to_bundle,
)

# Space-Track login endpoint for one session per run.
SPACETRACK_LOGIN_URL = "https://www.space-track.org/ajaxauth/login"
# Space-Track logout endpoint to end the session after the run.
SPACETRACK_LOGOUT_URL = "https://www.space-track.org/ajaxauth/logout"
# Pause between Space-Track queries to stay below the service limits.
SPACETRACK_QUERY_DELAY_SECONDS = 3


def print_actions_annotation(level: str, message: str) -> None:
    """Print a GitHub Actions annotation when running in Actions."""
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::{level}::{message}")


def load_credentials_from_secrets():
    """
    Load Space-Track credentials from .streamlit/secrets.toml file.
    
    Returns:
        tuple: (username, password) or (None, None) if not found
    """
    secrets_path = Path(__file__).parent.parent / ".streamlit" / "secrets.toml"
    
    if not secrets_path.exists():
        return None, None
    
    try:
        # Try using tomllib (Python 3.11+)
        try:
            import tomllib
            with open(secrets_path, 'rb') as f:
                secrets = tomllib.load(f)
        except ImportError:
            # Fallback to toml package
            try:
                import toml
                secrets = toml.load(secrets_path)
            except ImportError:
                # Simple manual parsing for nested TOML
                secrets = {}
                current_section = None
                with open(secrets_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('[') and line.endswith(']'):
                            current_section = line[1:-1]
                            secrets[current_section] = {}
                        elif '=' in line and not line.startswith('#'):
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip().strip('"').strip("'")
                            if current_section:
                                secrets[current_section][key] = value
                            else:
                                secrets[key] = value
        
        # Check for nested [spacetrack] section first
        if 'spacetrack' in secrets:
            username = secrets['spacetrack'].get('username')
            password = secrets['spacetrack'].get('password')
            if username and password:
                return username, password
        
        # Fall back to flat keys
        username = secrets.get('SPACETRACK_USERNAME') or secrets.get('spacetrack_username')
        password = secrets.get('SPACETRACK_PASSWORD') or secrets.get('spacetrack_password')
        
        return username, password
    except Exception as e:
        print(f"⚠️  Could not read secrets.toml: {e}")
        return None, None


def fetch_gp_history_for_satellite(
    session: requests.Session, norad_id: int, start_date: str, end_date: str
) -> list:
    """
    Fetch GP history for a single satellite from Space-Track.
    
    Returns:
        List of GP records as dicts
    """
    gp_url = (
        f"https://www.space-track.org/basicspacedata/query/class/gp_history/"
        f"EPOCH/{start_date}--{end_date}/NORAD_CAT_ID/{norad_id}/orderby/EPOCH asc/format/json"
    )

    resp = session.get(gp_url, timeout=120)
    if resp.status_code != 200:
        error = requests.HTTPError(f"Failed to fetch GP data for {norad_id}: HTTP {resp.status_code}")
        error.response = resp
        raise error

    return resp.json()


def parse_epoch(epoch: str):
    """Parse an EPOCH string into an aware UTC datetime."""
    if not epoch:
        return None
    try:
        at = datetime.fromisoformat(epoch.replace("Z", "+00:00"))
    except ValueError:
        return None
    # Space-Track's EPOCH carries no offset and is UTC; read as local time it would shift by hours.
    return (at if at.tzinfo else at.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def newest_epoch_date(rows: list) -> str | None:
    """Return YYYY-MM-DD for the newest EPOCH in rows."""
    newest = None
    for row in rows:
        parsed = parse_epoch(row.get("EPOCH"))
        if parsed and (newest is None or parsed > newest):
            newest = parsed
    if newest is None:
        return None
    return newest.strftime("%Y-%m-%d")


def merge_rows_by_epoch(existing_rows: list, new_rows: list, cutoff: datetime) -> list:
    """Merge GP rows by EPOCH, keep the newest value per EPOCH, oldest first."""
    deduped = {}
    epochs = {}
    for row in existing_rows:
        epoch = row.get("EPOCH")
        parsed = parse_epoch(epoch)
        if epoch and parsed and parsed >= cutoff:
            deduped[epoch] = row
            epochs[epoch] = parsed
    for row in new_rows:
        epoch = row.get("EPOCH")
        parsed = parse_epoch(epoch)
        if epoch and parsed and parsed >= cutoff:
            deduped[epoch] = row
            epochs[epoch] = parsed
    ordered_epochs = sorted(epochs.keys(), key=lambda epoch: epochs[epoch])
    return [deduped[epoch] for epoch in ordered_epochs]


def is_busy_error(error: Exception) -> bool:
    """True when Space-Track asked us to back off for this run."""
    if isinstance(error, (requests.Timeout, requests.ConnectionError)):
        return True
    if isinstance(error, requests.HTTPError):
        response = getattr(error, "response", None)
        status_code = getattr(response, "status_code", None)
        if status_code == 429:
            return True
        if isinstance(status_code, int) and 500 <= status_code <= 599:
            return True
    return False


def update_constellation_tles(constellation_name: str, sat_dict: dict, verbose: bool = True):
    """
    Update bundled TLE data for a constellation using CelesTrak.
    
    Args:
        constellation_name: 'navic', 'qzss', or 'beidou3'
        sat_dict: Dictionary of satellite_name -> norad_id
        verbose: Print progress messages
    """
    if verbose:
        print(f"\n{'='*60}")
        print(f"Updating TLEs for {constellation_name.upper()}")
        print(f"{'='*60}")
    
    norad_ids = [nid for nid in sat_dict.values() if nid is not None]
    
    if verbose:
        print(f"Fetching TLEs for {len(norad_ids)} satellites from CelesTrak...")
    
    tle_data = fetch_tles_from_celestrak(norad_ids, timeout=30)
    
    if not tle_data:
        print(f"⚠️  Failed to fetch TLEs for {constellation_name}")
        return False
    
    success = save_tles_to_bundle(constellation_name, tle_data, sat_dict)
    
    if success and verbose:
        print(f"✅ Saved TLEs for {constellation_name} ({len(norad_ids)} satellites)")
    
    return success


def update_constellation_gp_history(
    constellation_name: str,
    sat_dict: dict,
    session: requests.Session,
    days: int = 365,
    verbose: bool = True,
    query_state: dict | None = None,
):
    """
    Update bundled GP history data for a constellation using Space-Track.
    
    Args:
        constellation_name: 'navic', 'qzss', or 'beidou3'
        sat_dict: Dictionary of satellite_name -> norad_id
        session: Authenticated Space-Track session
        days: Number of days of history to fetch (default: 365 for full year pattern analysis)
        verbose: Print progress messages
    """
    if query_state is None:
        query_state = {"queries_made": 0}

    if verbose:
        print(f"\n{'='*60}")
        print(f"Updating GP History for {constellation_name.upper()}")
        print(f"{'='*60}")

    end_date = datetime.now(timezone.utc)
    # From midnight, as the whole-window download did, so no row of the first day is dropped.
    cutoff_date = (end_date - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff_str = cutoff_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    if verbose:
        print(f"Date range: {cutoff_str} to {end_str}")

    bundled = load_bundled_gp_history(constellation_name)
    existing_data = bundled.get("satellites", {}) if isinstance(bundled, dict) else {}
    satellite_data = {}

    sat_items = [(sat_name, norad_id) for sat_name, norad_id in sat_dict.items() if norad_id is not None]
    total_satellites = len(sat_items)
    processed_satellites = 0
    busy_stop = False

    for index, (sat_name, norad_id) in enumerate(sat_items):
        existing_rows = list(existing_data.get(sat_name, []))
        newest = newest_epoch_date(existing_rows)
        start_str = max(newest, cutoff_str) if newest else cutoff_str   # never more than the window

        if query_state["queries_made"] > 0:
            time.sleep(SPACETRACK_QUERY_DELAY_SECONDS)
        query_state["queries_made"] += 1

        try:
            records = fetch_gp_history_for_satellite(
                session, norad_id, start_str, end_str
            )
            satellite_data[sat_name] = merge_rows_by_epoch(existing_rows, records, cutoff_date)
            processed_satellites += 1
        except Exception as e:
            satellite_data[sat_name] = existing_rows
            if verbose:
                print(f"     ⚠️  Error for {sat_name}: {e}")
            if is_busy_error(e):
                busy_stop = True
                for remaining_name, _ in sat_items[index + 1 :]:
                    satellite_data[remaining_name] = list(existing_data.get(remaining_name, []))
                break

    for sat_name, _ in sat_items:
        satellite_data.setdefault(sat_name, list(existing_data.get(sat_name, [])))

    success = save_gp_history_to_bundle(
        constellation_name, satellite_data, cutoff_str, end_str
    )

    if success and verbose and not busy_stop:
        total_records = sum(len(r) for r in satellite_data.values())
        print(f"✅ Saved GP history for {constellation_name} ({total_records} total records)")

    return {
        "saved": success,
        "busy_stop": busy_stop,
        "processed_satellites": processed_satellites,
        "total_satellites": total_satellites,
    }


def resolve_targets(constellation_arg: str) -> dict:
    """Resolve the selected constellation argument into target satellite groups."""
    constellations = {
        "navic": NAVIK_SATS,
        "qzss": QZSS_SATS,
        "beidou3": BEIDOU3_SATS,
    }
    meo = {system.lower(): sats for system, sats in MEO_SATS.items()}
    all_constellations = {**constellations, **meo}
    if constellation_arg == "all":
        return constellations
    return {constellation_arg: all_constellations[constellation_arg]}


def main():
    parser = argparse.ArgumentParser(
        description="Update bundled TLE and GP history data for offline dashboard."
    )
    parser.add_argument('--username', '-u', 
                        default=os.environ.get('SPACETRACK_USERNAME'),
                        help='Space-Track username (or set SPACETRACK_USERNAME env var)')
    parser.add_argument('--password', '-p',
                        default=os.environ.get('SPACETRACK_PASSWORD'),
                        help='Space-Track password (or set SPACETRACK_PASSWORD env var)')
    parser.add_argument('--days', '-d', type=int, default=365,
                        help='Days of GP history to fetch (default: 365 for full year)')
    parser.add_argument('--constellation', '-c', 
                        choices=['navic', 'qzss', 'beidou3', 'gps', 'glonass', 'galileo', 'all'],
                        default='all',
                        help='Constellation to update (default: all)')
    parser.add_argument('--tles-only', action='store_true',
                        help='Only update TLEs (skip GP history)')
    parser.add_argument('--history-only', action='store_true',
                        help='Only update GP history (skip TLEs)')
    
    args = parser.parse_args()
    
    # Try to get credentials from various sources
    username = args.username
    password = args.password

    # If not provided via CLI/env, try secrets.toml
    if not username or not password:
        secrets_username, secrets_password = load_credentials_from_secrets()
        if secrets_username and secrets_password:
            print("📂 Using credentials from .streamlit/secrets.toml")
            username = secrets_username
            password = secrets_password

    targets = resolve_targets(args.constellation)

    print(f"\n🛰️  GNSS Health Monitor - Data Update Script")
    print(f"   Timestamp: {datetime.now(timezone.utc).isoformat()}")

    # Update TLEs (uses CelesTrak, no auth needed)
    if not args.history_only:
        print("\n" + "="*60)
        print("UPDATING TLE DATA (CelesTrak)")
        print("="*60)

        for name, sat_dict in targets.items():
            update_constellation_tles(name, sat_dict)

    exit_code = 0
    should_run_history = not args.tles_only
    has_login = bool(username and password)

    if should_run_history and not has_login:
        message = "Space-Track: no login set; orbit history not updated, CelesTrak orbit records only"
        print(message)
        print_actions_annotation("notice", message)

    # Update GP History (uses Space-Track, auth required)
    if should_run_history and has_login:
        print("\n" + "="*60)
        print("UPDATING GP HISTORY DATA (Space-Track)")
        print("="*60)

        total_satellites = sum(
            1 for sat_dict in targets.values() for norad_id in sat_dict.values() if norad_id is not None
        )
        processed_satellites = 0
        busy_stop = False
        login_refused = False
        save_failed = False

        session = requests.Session()
        try:
            try:
                response = session.post(
                    SPACETRACK_LOGIN_URL,
                    data={"identity": username, "password": password},
                    timeout=30,
                )
            except requests.RequestException:
                response = None   # Space-Track did not answer: busy, never retried
            if response is None or response.status_code == 429 or response.status_code >= 500:
                busy_stop = True
            elif response.status_code != 200 or "Login Failed" in response.text:
                login_refused = True
            else:
                query_state = {"queries_made": 0}
                for name, sat_dict in targets.items():
                    result = update_constellation_gp_history(
                        name,
                        sat_dict,
                        session,
                        days=args.days,
                        query_state=query_state,
                    )
                    processed_satellites += result["processed_satellites"]
                    if not result["saved"]:
                        save_failed = True
                    if result["busy_stop"]:
                        busy_stop = True
                        break
        finally:
            try:
                session.get(SPACETRACK_LOGOUT_URL, timeout=30)
            except Exception:
                pass

        if login_refused:
            message = "Space-Track: login refused; orbit history not updated"
            print(message)
            print_actions_annotation("error", message)
            exit_code = 2
        if save_failed:
            message = "Orbit history could not be saved; see the errors above"
            print(message)
            print_actions_annotation("error", message)
            exit_code = 2
        if busy_stop:
            message = (
                f"Space-Track: busy; stopped after {processed_satellites} of {total_satellites} satellites"
            )
            print(message)
            print_actions_annotation("warning", message)

    print("\n" + "="*60)
    print("✅ DATA UPDATE COMPLETE" if exit_code == 0 else "⚠️ DATA UPDATE FINISHED WITH PROBLEMS (see above)")
    print("="*60)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
