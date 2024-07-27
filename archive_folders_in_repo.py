import os
import shutil
import subprocess
from datetime import datetime, timedelta

# Define the path to the git repository
repo_path = '/mnt/c/proj/euc/data_jira-ticket-code'
archive_path = '/mnt/c/proj/euc/data_jira-ticket-code/archive'
os.makedirs(archive_path, exist_ok=True)

# Get the date three months ago
three_months_ago = datetime.now() - timedelta(days=180)
since_date = three_months_ago.strftime('%Y-%m-%d')

def get_changed_dirs(repo_path, until_date):
    # Get the list of folders changed before the given date
    cmd = ['git', 'log', '--until', until_date, '--name-only', '--pretty=format:']
    result = subprocess.run(cmd, cwd=repo_path, stdout=subprocess.PIPE, text=True)
    changed_files = result.stdout.splitlines()
    
    # Extract unique directories from the list of changed files
    changed_dirs = set()
    for file in changed_files:
        if file:
            dir_path = os.path.join(repo_path, os.path.dirname(file))
            while dir_path != repo_path and dir_path not in changed_dirs:
                if 'archive' in dir_path or '.git' in dir_path or '"' in dir_path or dir_path == '/mnt/c/proj/euc/data_jira-ticket-code/':
                    break
                changed_dirs.add(dir_path)
                dir_path = os.path.dirname(dir_path)
    
    changed_dirs = sorted(changed_dirs)
    return changed_dirs

def get_changed_dirs_since(repo_path, since_date):
    # Get the list of folders changed since the given date
    cmd = ['git', 'log', '--since', since_date, '--name-only', '--pretty=format:']
    result = subprocess.run(cmd, cwd=repo_path, stdout=subprocess.PIPE, text=True)
    changed_files = result.stdout.splitlines()
    
    # Extract unique directories from the list of changed files
    changed_dirs = set()
    for file in changed_files:
        if file:
            dir_path = os.path.join(repo_path, os.path.dirname(file))
            while dir_path != repo_path and dir_path not in changed_dirs:
                changed_dirs.add(dir_path)
                dir_path = os.path.dirname(dir_path)
    
    return changed_dirs

def move_old_folders(repo_path, archive_path, changed_dirs_before, changed_dirs_after):
    for item in os.listdir(repo_path):
        item_path = os.path.join(repo_path, item)
        if os.path.isdir(item_path) and item_path in changed_dirs_before and item_path not in changed_dirs_after:
            # Move the folder to the archive using Git (to retain file history)
            subprocess.run(['git', 'mv', item_path, archive_path], cwd=repo_path)
            # shutil.move(item_path, os.path.join(archive_path, item))
            print(f"Moved {item_path}")

# Get the changed folders before the specified date, excluding the 'archive' subfolder
changed_dirs_before = get_changed_dirs(repo_path, since_date)

# Get the changed folders since the specified date
changed_dirs_after = get_changed_dirs_since(repo_path, since_date)

# Move folders that were changed before the specified date but not after
move_old_folders(repo_path, archive_path, changed_dirs_before, changed_dirs_after)
