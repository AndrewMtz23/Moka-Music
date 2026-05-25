import io
from pathlib import Path
from typing import Optional

from PIL import Image, UnidentifiedImageError

from app.constants import FileFormats


PREFERRED_COVER_NAMES = (
    "cover",
    "folder",
    "front",
    "album",
    "artwork",
    "portada",
    "caratula",
)


def process_cover_image(image_path: str | Path, *, max_size: tuple[int, int] = (800, 800), quality: int = 90) -> Optional[bytes]:
    try:
        with Image.open(image_path) as image:
            if image.mode != "RGB":
                image = image.convert("RGB")
            image.thumbnail(max_size, Image.LANCZOS)
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=quality)
            return output.getvalue()
    except (UnidentifiedImageError, OSError):
        return None


def find_folder_cover(audio_path: str | Path) -> Optional[str]:
    folder = Path(audio_path).parent
    if not folder.exists():
        return None
    image_paths = [
        item
        for item in folder.iterdir()
        if item.is_file() and item.suffix.lower() in FileFormats.IMAGES
    ]
    if not image_paths:
        return None
    for preferred in PREFERRED_COVER_NAMES:
        for image_path in image_paths:
            if preferred in image_path.stem.lower():
                return str(image_path)
    image_paths.sort(key=lambda path: path.stat().st_size, reverse=True)
    return str(image_paths[0])
