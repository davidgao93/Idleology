import requests

def get_album_images(album_id, access_token):
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    
    url = f'https://api.imgur.com/3/album/{album_id}/images'
    response = requests.get(url, headers=headers)
    response.raise_for_status()  # Raise an error for bad responses
    images = response.json().get('data', [])
    
    return images

def save_images_with_names_or_titles(images, filename='images.txt'):
    with open(filename, 'w') as file:
        for image in images:
            image_url = image['link']
            # Use the 'name' if available; otherwise fallback to 'title'
            name = image['name'] if image['name'] else (image['title'] if image['title'] else "No Name")
            # Format the name/title for better readability
            formatted_name = name.replace('-', ' ').replace('.png', '').replace('.jpg', '').replace('.jpeg', '').title()

            # Save the name/title and URL to the file
            file.write(f"{formatted_name}: {image_url}\n")

def main():
    album_id = 'NZZFWxN'  # Replace with the Imgur album ID
    access_token = '13767a4ef279ce38ecf274e0a99b065390fdc4f6'  # Replace with your access token

    images = get_album_images(album_id, access_token)
    save_images_with_names_or_titles(images)

    print(f"Saved {len(images)} images to images.txt")

if __name__ == '__main__':
    main()