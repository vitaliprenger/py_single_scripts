from msal import PublicClientApplication
import requests

tenant_id = 'b58815b9-1d99-470a-a2b1-b3fd7f663db6'
client_id = '85f7847a-ffc3-4b0b-8980-c7b8b02781ca'
client_secret = '...'
authority = f'https://login.microsoftonline.com/{tenant_id}'
scopes = ['Calendars.Read']

app = PublicClientApplication(client_id, authority=authority)

# Utilize device code flow
flow = app.initiate_device_flow(scopes=scopes)

if 'user_code' not in flow:
    raise Exception('Failed to create device flow: {}'.format(flow.get('error')))

print(flow['message'])  # Displaying the code message for the user to follow

token = app.acquire_token_by_device_flow(flow)  # Wait for user authentication
if 'access_token' in token:
    headers = {'Authorization': f"Bearer {token['access_token']}"}
    url = 'https://graph.microsoft.com/v1.0/me/events'
    response = requests.get(url, headers=headers)
    
    if response.ok:
        events = response.json()
        print(events)
    else:
        print("Error retrieving events:", response.json())
else:
    print("Token acquisition failed:", token.get("error_description"))