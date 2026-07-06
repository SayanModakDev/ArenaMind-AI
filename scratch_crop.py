import sys
from PIL import Image

def main():
    img = Image.open('static/logo.png').convert("RGBA")
    data = img.load()
    width, height = img.size
    
    # We assume the top-left pixel is the background color
    bg_color = data[0, 0]
    
    # Define a tolerance
    tol = 50
    
    # Find bounding box of non-background
    min_x, min_y, max_x, max_y = width, height, 0, 0
    
    for y in range(height):
        for x in range(width):
            r, g, b, a = data[x, y]
            # check distance
            if abs(r - bg_color[0]) > tol or abs(g - bg_color[1]) > tol or abs(b - bg_color[2]) > tol:
                if x < min_x: min_x = x
                if y < min_y: min_y = y
                if x > max_x: max_x = x
                if y > max_y: max_y = y

    print(f"Bounding box: {min_x}, {min_y}, {max_x}, {max_y}")
    
    if min_x >= max_x or min_y >= max_y:
        print("Could not find image bounds (maybe entirely background).")
        sys.exit(1)
        
    # Crop
    img_cropped = img.crop((min_x, min_y, max_x+1, max_y+1))
    
    # Make background transparent in cropped image
    data_crop = img_cropped.load()
    c_width, c_height = img_cropped.size
    for y in range(c_height):
        for x in range(c_width):
            r, g, b, a = data_crop[x, y]
            if abs(r - bg_color[0]) <= tol and abs(g - bg_color[1]) <= tol and abs(b - bg_color[2]) <= tol:
                data_crop[x, y] = (r, g, b, 0)
                
    img_cropped.save('static/logo.png')
    print("Cropped and saved successfully.")

if __name__ == "__main__":
    main()
