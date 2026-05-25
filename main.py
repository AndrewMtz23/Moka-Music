import logging
import os
import sys

from app.constants import APP_NAME, LOG_FILE, LOG_FORMAT


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def check_dependencies() -> tuple[bool, list[str]]:
    required_packages = [
        ("pygame", "pygame"),
        ("PIL", "Pillow"),
        ("eyed3", "eyed3"),
        ("mutagen", "mutagen"),
        ("tkinterdnd2", "tkinterdnd2"),
        ("send2trash", "Send2Trash"),
    ]

    missing: list[str] = []
    for package_name, pip_name in required_packages:
        try:
            __import__(package_name)
        except ImportError:
            missing.append(pip_name)

    return (len(missing) == 0, missing)


def main() -> int:
    setup_logging()
    logger = logging.getLogger(__name__)

    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)

    ok, missing = check_dependencies()
    if not ok:
        print(f"{APP_NAME} is missing dependencies:")
        for package in missing:
            print(f"  - {package}")
        print("\nInstall them with:")
        print(f"  pip install {' '.join(missing)}")
        return 1

    try:
        from app.ui import iniciar_app

        logger.info("Starting %s", APP_NAME)
        iniciar_app()
        return 0
    except ImportError as exc:
        logger.exception("Import error while starting the app")
        print(f"Import error: {exc}")
        print("Check requirements.txt and your Python environment.")
        return 1
    except Exception as exc:
        logger.exception("Unexpected startup error")
        print(f"Unexpected error: {exc}")
        print(f"See {LOG_FILE} for details.")
        return 1
    finally:
        logger.info("Application finished")


if __name__ == "__main__":
    raise SystemExit(main())
