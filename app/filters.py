from pathlib import Path


def normalize_filename(filename: str | None) -> str:
    if not filename:
        return ""

    return filename.strip()


def get_extension(filename: str | None) -> str:
    filename = normalize_filename(filename)

    if not filename:
        return ""

    return Path(filename).suffix.lower()


def is_blocked_filename(
    filename: str | None,
    blocked_extensions: set[str] | frozenset[str],
) -> bool:

    extension = get_extension(filename)

    if not extension:
        return False

    return extension in blocked_extensions