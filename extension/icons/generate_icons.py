"""Generate extension icons."""

import os

from PIL import Image, ImageDraw


def create_icon(size):
    """Create a simple AI detector icon at the specified size."""
    # Create image with transparent background
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Calculate dimensions
    padding = size // 8
    center = size // 2

    # Draw background circle (blue gradient effect)
    circle_radius = (size - 2 * padding) // 2
    draw.ellipse(
        [padding, padding, size - padding, size - padding],
        fill=(59, 130, 246, 255)  # Blue
    )

    # Draw inner "AI" text representation as stylized eye
    eye_size = circle_radius // 2

    # Draw scanning lines
    line_color = (255, 255, 255, 200)
    line_width = max(1, size // 32)

    for i in range(-2, 3):
        y = center + i * (eye_size // 3)
        x_offset = abs(i) * (eye_size // 4)
        draw.line(
            [(center - eye_size + x_offset, y), (center + eye_size - x_offset, y)],
            fill=line_color,
            width=line_width
        )

    # Draw center dot (AI detection point)
    dot_radius = max(2, size // 16)
    draw.ellipse(
        [center - dot_radius, center - dot_radius,
         center + dot_radius, center + dot_radius],
        fill=(255, 255, 255, 255)
    )

    return img


def main():
    """Generate icons in all required sizes."""
    sizes = [16, 48, 128]
    script_dir = os.path.dirname(os.path.abspath(__file__))

    for size in sizes:
        icon = create_icon(size)
        filename = f"icon-{size}.png"
        filepath = os.path.join(script_dir, filename)
        icon.save(filepath, 'PNG')
        print(f"Created {filename}")


if __name__ == "__main__":
    main()
