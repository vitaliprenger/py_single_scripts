import config
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
                   print(f"Skipping {name_tech} as it's already cloned.")

           page += 1

       subgroups = group.subgroups.list()
       for subgroup in subgroups:
           print(f"Fetching projects from subgroup: {subgroup.name}")
           fetch_projects(subgroup)


if __name__ == '__main__':
   api_token = config.eucon_gitlab_api_token
   gitlaburl = 'https://gitlab.eucon-services.com'
   
   # private token or personal token authentication (self-hosted GitLab instance)
   gl = gitlab.Gitlab(url=gitlaburl, private_token=api_token)

   # make an API request to create the gl.user object. This is not required but may be useful
   # to validate your token authentication. Note that this will not work with job tokens.
   gl.auth()

   # Enable "debug" mode. This can be useful when trying to determine what
   # information is being sent back and forth to the GitLab server.
   # Note: this will cause credentials and other potentially sensitive
   # information to be printed to the terminal.
   # gl.enable_debug()
   
   projects = gl.projects.list(iterator=True)  
   # for project in projects:
   #    print(project) 
      
   path = '/mnt/c/proj/euc'
   print(path)
   
   # group = gl.groups.get(158) # 160 = SSIS-Pakete # 158 = Team-Data
   # group_childs = group.descendant_groups.list()
   
   group = gl.groups.get(160) # 160 = SSIS-Pakete # 158 = Team-Data # 170 = SSRS-Berichte
   subfolder = group.path
   
   fetch_projects(group)

