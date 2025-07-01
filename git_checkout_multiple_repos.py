import helper.config as config
import gitlab
import subprocess
import os
from datetime import datetime, timedelta
import shutil  # Import shutil for deleting directories

def handle_remove_readonly(func, path, exc_info):
    import stat
    if not os.access(path, os.W_OK):
        os.chmod(path, stat.S_IWUSR)
        func(path)
    else:
        raise

def fetch_projects(base_path, group, fetch_subfolder, include_archived=False, include_old=False, skipped_old_projects=None):
    if skipped_old_projects is None:
        skipped_old_projects = []
    page = 1
    per_page = 100

    while True:
        projects = group.projects.list(per_page=per_page, page=page)
        if not projects:
            break

        for project in projects:
            project_path = os.path.join(base_path, fetch_subfolder, project.path + '.git')
            last_two_years = (datetime.now() - timedelta(days=2*365)).strftime('%Y-%m-%d')
            last_activity = project.attributes['last_activity_at'][:10]
            is_archived = project.attributes['archived']
            is_old = last_activity < last_two_years
            is_active = not is_archived and not is_old

            if (include_archived and is_archived) or (include_old and is_old) or is_active:
                if not os.path.exists(project_path):
                    print(f"Cloning {project.path}...")
                    subprocess.call(['git', 'clone', project.http_url_to_repo, project_path])
                else:
                    print(f"Updating {project.path} at {project_path}...")
                    subprocess.call(['git', '-C', project_path, 'checkout', 'master'])
                    subprocess.call(['git', '-C', project_path, 'pull'])
            elif is_old and not is_archived:
                skipped_old_projects.append(f"{project.path} (last activity: {last_activity})")
                if os.path.exists(project_path):
                    print(f"Deleting old project {project.path} at {project_path}...")
                    shutil.rmtree(project_path, onerror=handle_remove_readonly)
            elif os.path.exists(project_path):
                print(f"Deleting archived/old project {project.path} at {project_path}...")
                shutil.rmtree(project_path, onerror=handle_remove_readonly)

        page += 1
    
    # process subgroups
    print(f"Fetching subgroups for group: {group.name}")
    subgroups = group.subgroups.list()
    for subgroup in subgroups:
        print(f"Fetching projects from subgroup: {subgroup.name}")
        new_group = gl.groups.get(subgroup.id)
        if fetch_subfolder:
            # If fetch_subfolder is provided, append subgroup path to it
            new_subfolder = os.path.join(fetch_subfolder, subgroup.path)
        else:
            new_subfolder = subgroup.path
        # Set include_old True for specific subgroups
        if subgroup.full_path in ["digital/insurance/team-data", "digital/insurance/team-data-obungi"]: # data groups where old projects are interesting
            fetch_projects(base_path, new_group, new_subfolder, include_archived, True, skipped_old_projects)
        elif subgroup.full_path in ["digital/insurance/predictiveanalytics", "digital/insurance/camunda-hackday", "digital/insurance/choreography",
                                     "digital/insurance/property", "digital/insurance/car"]: # uninteresting subgroups
            print(f"Skipping further subgroups under {subgroup.full_path}")
            continue
        else:
            fetch_projects(base_path, new_group, new_subfolder, include_archived, include_old, skipped_old_projects)

    return skipped_old_projects


if __name__ == '__main__':
    api_token = config.eucon_gitlab_api_token
    gitlaburl = 'https://gitlab.eucon-services.com'

    gl = gitlab.Gitlab(url=gitlaburl, private_token=api_token)

    gl.auth()
    projects = gl.projects.list(iterator=True)

# Uncomment the appropriate path based on your environment
#    base_path = 'C:\\Users\\vitali_prenger\\repos' -- 
#    base_path = 'C:\\Users\\vitali_prenger_ext\\repos' -- ssis vm
#    base_path = '/mnt/c/proj/euc' # Laptop Vit WSL
    # Always map 'digital' to 'C:\\proj\\euc'
    base_path = 'C:\\proj\\euc'

    # https://gitlab.eucon-services.com/digital/insurance
    # 42 = digital -> 43 = shared | 53 = Insurance -> 158 = Team-Data | 1550 = team-data-obungi | 172 = multi-domain-case-suite | 56 = shared
    group = gl.groups.get(158)

    # Remove 'digital/' prefix from group.full_path if present
    group_path = group.full_path
    if group_path.startswith('digital/'):
        subfolder = group_path[len('digital/'):]
    elif group_path.startswith('digital'):
        subfolder = group_path[len('digital'):]
    else:
        subfolder = group_path

    skipped_old_projects = fetch_projects(base_path, group=group, fetch_subfolder=subfolder, include_archived=False, include_old=True)
    
    if skipped_old_projects:
        print("\nProjects skipped because they are too old:")
        for proj in skipped_old_projects:
            print(proj)
    else:
        print("\nNo old projects were skipped.")

