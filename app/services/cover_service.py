import io
from pathlib import Path
from typing import Optional

from PIL import Image, ImageOps, UnidentifiedImageError

from app.constants import FileFormats


COVER_FILENAME = "PORTADA.jpg"

PREFERRED_COVER_NAMES = (
    "portada",
    "cover",
    "folder",
    "front",
    "album",
    "artwork",
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


def replace_folder_cover(
    image_path: str | Path,
    folder: str | Path,
    *,
    filename: str = COVER_FILENAME,
    size: tuple[int, int] = (800, 800),
    quality: int = 90,
) -> Optional[str]:
    folder_path = Path(folder)
    if not folder_path.exists() or not folder_path.is_dir():
        return None

    source = Path(image_path)
    destination = folder_path / filename
    try:
        for image_file in folder_path.iterdir():
            if image_file.is_file() and image_file.suffix.lower() in FileFormats.IMAGES:
                if (
                    image_file.stem.lower() == Path(filename).stem.lower()
                    and image_file != destination
                    and image_file.resolve() != source.resolve()
                ):
                    image_file.unlink()

        with Image.open(source) as image:
            if image.mode != "RGB":
                image = image.convert("RGB")
            image = ImageOps.fit(image, size, method=Image.LANCZOS)
            image.save(destination, format="JPEG", quality=quality)
        return str(destination)
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
