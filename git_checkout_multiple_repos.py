import helper.config as config
import gitlab
import subprocess
import os

def fetch_projects(group):
    page = 1
    per_page = 100

    while True:
        projects = group.projects.list(per_page=per_page, page=page)
        if not projects:
            break

        for project in projects:
            git_url = project.http_url_to_repo
            name_tech = project.path
            project_path = os.path.join(path, subfolder, name_tech + '.git')

            if not os.path.exists(project_path):
                print(f"Cloning {name_tech}...")
                subprocess.call(['git', 'clone', git_url, project_path])
            else:
                print(f"Repository {name_tech} already exists, updating...")
                os.chdir(project_path)  # Change directory to project_path
                # Check if any branch is currently checked out
                branch_output = subprocess.check_output(['git', 'branch', '--show-current']).decode().strip()
                if branch_output == '':
                    # No branch is checked out, checkout master
                    subprocess.call(['git', 'checkout', 'master'])
                subprocess.call(['git', 'pull'])  # Pull from current branch or master

        page += 1

    subgroups = group.subgroups.list()
    for subgroup in subgroups:
        print(f"Fetching projects from subgroup: {subgroup.name}")
        fetch_projects(subgroup)


if __name__ == '__main__':
   api_token = config.eucon_gitlab_api_token
   gitlaburl = 'https://gitlab.eucon-services.com'
   
   gl = gitlab.Gitlab(url=gitlaburl, private_token=api_token)

   gl.auth()
   
   projects = gl.projects.list(iterator=True)  
      

#    path = 'C:\\Users\\vitali_prenger\\repos' -- 
#    path = 'C:\\Users\\vitali_prenger_ext\\repos' -- ssis vm
   path = '/mnt/c/proj/euc' # Laptop Vit
   print(path)
   
   # 160 = SSIS-Pakete # 170 = SSRS-Berichte # 158 = Team-Data  # 1513 = Databases # 179 = Datenlieferung
   group = gl.groups.get(160) 
   subfolder = group.path
   
   fetch_projects(group)

