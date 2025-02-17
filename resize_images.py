import os
from PIL import Image

def resize_large_pngs(folder_path):
    # Loop through all files in the specified folder
    for filename in os.listdir(folder_path):
        # Check if the file is a .png file
        if filename.lower().endswith('.png'):
            file_path = os.path.join(folder_path, filename)
            # Check the file size
            if os.path.getsize(file_path) > 2 * 1024 * 1024:  # 2 Megabytes
                print(f"Resizing {filename}...")
                # Open the image
                with Image.open(file_path) as img:
                    # Resize the image (half of the original size)
                    new_size = (img.width // 2, img.height // 2)
                    resized_img = img.resize(new_size)
                    # Save the resized image
                    resized_img.save(file_path)  # Overwrites the original file
                print(f"Resized {filename} to {new_size[0]}x{new_size[1]}.")

# Specify the folder path
folder_path = 'C:\\Users\\dervd\\Documents\\Idleology\\assets\\images\\monsters'  # Change this to your folder path
resize_large_pngs(folder_path)