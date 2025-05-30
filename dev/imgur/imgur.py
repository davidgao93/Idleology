import requests

client_id = '00015ddf57ebace'
client_secret = '9194aeaea51f8c0cd637a1c0994f4736fc0cce90'
code = 'def7c85448a4c77887f85f572ffb14bc0556068a'

# Define the payload for the request
data = {
    'client_id': client_id,
    'client_secret': client_secret,
    'grant_type': 'authorization_code',
    'code': code
}

# Send the post request
response = requests.post('https://api.imgur.com/oauth2/token', data=data)
access_token = response.json().get('access_token')

print(f"Access Token: {access_token}")