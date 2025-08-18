#!/usr/bin/env python3

__version__ = "0.2.0"

import os
import sys
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple, Optional
from pathlib import Path
import requests


def error_exit(message: str) -> None:
    """Print error message and exit with status 1."""
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def get_linear_api_key() -> str:
    """Get Linear API key from environment variable or config file."""
    # First, try environment variable
    api_key = os.getenv('LINEAR_API_KEY')
    if api_key:
        return api_key
    
    # Fall back to config file
    config_dir = Path.home() / '.config' / 'linear-project-updates'
    config_file = config_dir / 'config'
    
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                content = f.read().strip()
                if content:
                    return content
        except Exception as e:
            print(f"Error reading config file {config_file}: {e}")
    
    # No API key found
    error_exit(f"""LINEAR_API_KEY not found.
Please either:
1. Set the environment variable: export LINEAR_API_KEY='your_api_key_here'
2. Create a config file at {config_file} containing your API key
   mkdir -p {config_dir}
   echo 'your_api_key_here' > {config_file}""")


def build_graphql_query() -> Tuple[str, Dict[str, Any]]:
    """Build the GraphQL query to fetch all project updates."""
    query = """
    query GetProjectUpdates {
      projectUpdates {
        nodes {
          id
          createdAt
          updatedAt
          body
          url
          user {
            name
            email
          }
          project {
            id
            name
            description
            state
            priority
            status {
              id
              name
              type
            }
          }
        }
      }
    }
    """
    
    return query, {}


def fetch_project_updates(api_key: str) -> List[Dict[str, Any]]:
    """Fetch project updates from Linear API."""
    url = "https://api.linear.app/graphql"
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json"
    }
    
    query, variables = build_graphql_query()
    
    payload = {
        "query": query,
        "variables": variables
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        # Print response details for debugging
        if response.status_code != 200:
            error_exit(f"HTTP Error {response.status_code}: {response.text}")
        
        data = response.json()
        
        if "errors" in data:
            error_messages = "\n".join(f"  - {error['message']}" for error in data["errors"])
            error_exit(f"GraphQL Errors:\n{error_messages}")
        
        return data["data"]["projectUpdates"]["nodes"]
    
    except requests.exceptions.RequestException as e:
        error_exit(f"Error making request to Linear API: {e}")
    except KeyError as e:
        error_exit(f"Unexpected response format: {e}\nResponse: {response.text}")


def format_date(iso_date: str) -> str:
    """Format ISO date string to readable format."""
    try:
        dt = datetime.fromisoformat(iso_date.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except ValueError:
        return iso_date


def is_update_recent(update: Dict[str, Any], days: int = 14) -> bool:
    """Check if update was created/modified within the last N days."""
    try:
        # Use updatedAt if available, otherwise fall back to createdAt
        date_str = update.get("updatedAt", update.get("createdAt", ""))
        if not date_str:
            return False
        
        update_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        cutoff_date = datetime.now().replace(tzinfo=update_date.tzinfo) - timedelta(days=days)
        return update_date >= cutoff_date
    except (ValueError, TypeError):
        return False


def get_project_priority_score(update: Dict[str, Any]) -> int:
    """Get project priority score from Linear API priority field.
    Linear priority values: 1 (Urgent), 2 (High), 3 (Medium), 4 (Low), 0 (No priority)
    Returns inverted score for sorting (higher numbers = higher priority)."""
    project = update.get("project", {})
    priority = project.get("priority")
    
    # Handle different priority values from Linear API
    if priority == 1:  # Urgent
        return 100
    elif priority == 2:  # High
        return 75
    elif priority == 3:  # Medium
        return 50
    elif priority == 4:  # Low
        return 25
    else:  # No priority set (0 or None)
        return 10


def is_project_in_progress_or_paused(update: Dict[str, Any]) -> bool:
    """Check if a project is in progress or paused based on actual Linear status."""
    project = update.get("project", {})
    status = project.get("status", {})
    state = project.get("state", "").lower()
    status_name = status.get("name", "").lower()
    
    # Include projects that are actively being worked on or paused
    # Based on actual Linear status data:
    # - "started" state = In Progress (should include)
    # - "planned" state + "Paused" status = Paused (should include) 
    # - "planned" state + "Planned" status = Planned work (should include)
    # - "backlog" state = Backlog (should exclude)
    
    if state == "started":  # In Progress
        return True
    elif state == "planned":
        # Include both "Paused" and "Planned" from planned state
        if status_name in ["paused", "planned"]:
            return True
    
    # Exclude backlog and any other states
    return False


def get_latest_update_per_project(updates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Group updates by project and return the latest update for each project."""
    project_updates = {}
    
    for update in updates:
        project = update.get("project", {})
        project_id = project.get("id")
        
        if not project_id:
            continue
            
        updated_at = update.get("updatedAt", update.get("createdAt", ""))
        
        # If we haven't seen this project or this update is newer
        if project_id not in project_updates:
            project_updates[project_id] = update
        else:
            # Compare dates to find the latest
            current_date = project_updates[project_id].get("updatedAt", project_updates[project_id].get("createdAt", ""))
            if updated_at > current_date:
                project_updates[project_id] = update
    
    # Sort by priority score (highest first), then by project name for consistency
    latest_updates = list(project_updates.values())
    latest_updates.sort(key=lambda x: (-get_project_priority_score(x), x.get("project", {}).get("name", "").lower()))
    
    return latest_updates


def print_project_updates(updates: List[Dict[str, Any]], *, include_updated: bool = False, bold_headers: bool = False) -> None:
    """Print project updates to console in a simplified format."""
    if not updates:
        return
    
    for update in updates:
        # Project name
        project = update.get("project", {})
        project_name = project.get('name', 'Unknown')
        
        # Create header with or without timestamp
        if include_updated:
            # Update date (prefer updatedAt over createdAt)
            updated_at = update.get("updatedAt", update.get("createdAt", ""))
            formatted_date = format_date(updated_at)
            if bold_headers:
                header = f"**{project_name} ({formatted_date})**"
            else:
                header = f"## {project_name} ({formatted_date})"
        else:
            if bold_headers:
                header = f"**{project_name}**"
            else:
                header = f"## {project_name}"
        
        # Update content
        body = update.get("body", "").strip()
        
        print(header)
        if body:
            print(f"{body}")
        else:
            print("No update text available")
        print()


def main() -> None:
    """Main function to orchestrate the project updates fetching."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Fetch Linear project updates')
    parser.add_argument('--version', '-v', action='version', version=f'linear-updates {__version__}')
    parser.add_argument('--in-progress-only', '-p', action='store_true', 
                       help='Only show updates from projects that are in progress or paused')
    parser.add_argument('--include-updated', '-u', action='store_true',
                       help='Include last updated timestamp in project headers')
    parser.add_argument('--bold-headers', '-b', action='store_true',
                       help='Use bold markdown headers instead of ## headers')
    parser.add_argument('--recent', '-r', action='store_true',
                       help='Only show updates from the last two weeks')
    args = parser.parse_args()
    
    # Get API key
    api_key = get_linear_api_key()
    
    # Fetch all updates
    all_updates = fetch_project_updates(api_key)
    
    # Get latest update per project
    latest_updates = get_latest_update_per_project(all_updates)
    
    # Filter for in-progress/paused projects if requested
    if args.in_progress_only:
        latest_updates = [update for update in latest_updates 
                         if is_project_in_progress_or_paused(update)]
    
    # Filter for recent updates if requested
    if args.recent:
        latest_updates = [update for update in latest_updates 
                         if is_update_recent(update)]
    
    # Print results
    print_project_updates(latest_updates, include_updated=args.include_updated, bold_headers=args.bold_headers)


if __name__ == "__main__":
    main()