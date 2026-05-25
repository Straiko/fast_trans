import os

from PIL import Image, ImageDraw


def create_squircle_mask(size, radius):
    """Creates a high-quality antialiased rounded rectangle mask."""
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask)
    # Draw a rounded rectangle
    # PIL's rounded_rectangle is available in newer Pillow versions
    draw.rounded_rectangle([12, 12, size[0] - 13, size[1] - 13], radius=radius, fill=255)
    return mask


def main():
    img_path = '/home/root2506/.gemini/antigravity-cli/brain/bfc1365f-bca6-45b8-b5fc-6006be566939/olympus_app_icon_1779716219368.png'
    if not os.path.exists(img_path):
        print(f'Error: image not found at {img_path}')
        return

    img = Image.open(img_path)
    width, height = img.size
    print(f'Original size: {width}x{height}')

    # We crop the central 784x784 region
    # Center is (512, 512).
    # Left = 512 - 392 = 120
    # Top = 512 - 392 = 120
    # Right = 512 + 392 = 904
    # Bottom = 512 + 392 = 904
    left = 120
    top = 120
    right = 904
    bottom = 904

    cropped = img.crop((left, top, right, bottom))
    cropped = cropped.resize((512, 512), Image.Resampling.LANCZOS)

    # Apply a transparent squircle mask to remove the background outside the icon
    # Standard macOS squircle radius is about 115 pixels for a 512x512 icon
    mask = create_squircle_mask((512, 512), radius=110)

    # Convert cropped image to RGBA if not already
    cropped_rgba = cropped.convert('RGBA')

    # Create final transparent image
    final_img = Image.new('RGBA', (512, 512), (0, 0, 0, 0))
    final_img.paste(cropped_rgba, (0, 0), mask=mask)

    # Save as icon_new.png
    target_png = '/home/root2506/fast_trans1/icon_new.png'
    final_img.save(target_png, 'PNG')
    print(f'Saved cropped and masked icon to {target_png}')

    # Also save as icon_new.ico (multi-size ICO file for Windows)
    target_ico = '/home/root2506/fast_trans1/icon_new.ico'
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

    # For ICO, we want to scale final_img down to these sizes
    icon_images = []
    for size in sizes:
        icon_images.append(final_img.resize(size, Image.Resampling.LANCZOS))

    final_img.save(target_ico, format='ICO', sizes=sizes)
    print(f'Saved transparent ICO version to {target_ico}')


if __name__ == '__main__':
    main()
