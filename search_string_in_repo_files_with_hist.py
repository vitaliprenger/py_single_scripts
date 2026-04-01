import os
import subprocess


def search_string_in_repo(repo_path, search_string):
    os.chdir(repo_path)
    subprocess.run(["git", "fetch", "--all"])
    subprocess.run(["git", "checkout", "--force", "origin/master"])

    # Use a text search tool like grep
    result = subprocess.run(
        ["grep", "-r", "-i", search_string, "."], capture_output=True, text=True
    )
    print(result.stdout)


# Example usage
basefolder_wsl = "/mnt/c/proj/euc/ssrs-pakete/"
basefolder_win = "C:\\proj\\euc\\insurance\\team-data\\ssrs-berichte"
basefolder = basefolder_win  # Change to basefolder_wsl if running in WSL
repositories = subfolders = [f.path for f in os.scandir(basefolder) if f.is_dir()]
search_string = "ckzahlenauswertung_Gesamt"

for repo in repositories:
    if repo.endswith("SSRS-OnPrem.git"):
        search_string_in_repo(repo, search_string)
