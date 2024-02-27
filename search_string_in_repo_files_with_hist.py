import os
import subprocess

def search_string_in_repo(repo_path, search_string):
    os.chdir(repo_path)
    subprocess.run(["git", "fetch", "--all"])
    subprocess.run(["git", "checkout", "--force", "origin/master"])

    # Use a text search tool like grep
    result = subprocess.run(["grep", "-r", "-i", search_string, "."], capture_output=True, text=True)
    print(result.stdout)

# Example usage
basefolder = '/mnt/c/proj/euc/ssis-pakete/'
repositories = subfolders = [f.path for f in os.scandir(basefolder) if f.is_dir()]
search_string = 'KL_neu'

for repo in repositories:
    search_string_in_repo(repo, search_string)
