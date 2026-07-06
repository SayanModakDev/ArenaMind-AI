from PIL import Image

def main():
    img = Image.open('static/logo.png').convert("RGBA")
    width, height = img.size
    
    # The image was already cropped vertically, making it 1019x422.
    # The logo icon is typically on the left side, occupying a square area matching the height.
    # So we crop the left-most 422x422 pixels.
    square_size = height
    img_cropped = img.crop((0, 0, square_size, height))
    
    # Crop any remaining transparent pixels to make it perfectly tight
    bbox = img_cropped.getbbox()
    if bbox:
        img_cropped = img_cropped.crop(bbox)
        
    img_cropped.save('static/logo_icon_only.png')
    print("Saved logo_icon_only.png")

if __name__ == "__main__":
    main()
