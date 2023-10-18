import config
import gitlab
import subprocess

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
      
   path = 'C:/Users/vitali.prenger/repos'
   print(path)
   
   # group = gl.groups.get(158) # 160 = SSIS-Pakete # 158 = Team-Data
   # group_childs = group.descendant_groups.list()
   
   group = gl.groups.get(160) # 160 = SSIS-Pakete # 158 = Team-Data # 170 = SSRS-Berichte
   subfolder = group.path
   
   page = 1
   per_page = 100  # You can adjust this to fetch more projects per page
   projects = gl.projects.list(group_id=group.id, per_page=per_page, page=page)
   
   while projects:
      for project in projects:
         git_url = project.http_url_to_repo
         name_tech = project.path
         print(path + '/' + subfolder + '/' + name_tech + '.git')
         subprocess.call(['git', 'clone', git_url, path + '/' + subfolder + '/' + name_tech + '.git'])
      
      page += 1
      projects = gl.projects.list(group_id=group.id, per_page=per_page, page=page)
