from pathlib import Path


# ============================================================
# NORMALIZE FILENAME
# ============================================================

def normalize_filename(
    filename: str | None,
) -> str:

    if not filename:
        return ""

    return (
        filename
        .strip()
        .replace("\\", "/")
        .split("/")[-1]
    )


# ============================================================
# GET ALL EXTENSIONS
# ============================================================

def get_all_extensions(
    filename: str | None,
) -> list[str]:

    name = normalize_filename(
        filename
    )

    if not name or name in {
        ".",
        "..",
    }:

        return []

    return [
        suffix.lower()
        for suffix in Path(name).suffixes
    ]


# ============================================================
# GET FINAL EXTENSION
# ============================================================

def get_extension(
    filename: str | None,
) -> str:

    extensions = get_all_extensions(
        filename
    )

    if not extensions:
        return ""

    return extensions[-1]


# ============================================================
# FIND BLOCKED EXTENSIONS
# ============================================================

def find_blocked_extensions(
    filename: str | None,
    blocked_extensions,
) -> list[str]:

    extensions = get_all_extensions(
        filename
    )

    return [
        extension
        for extension in extensions
        if extension in blocked_extensions
    ]


# ============================================================
# CHECK IF FILE IS BLOCKED
# ============================================================

def is_blocked_filename(
    filename: str | None,
    blocked_extensions,
) -> bool:

    return bool(
        find_blocked_extensions(
            filename,
            blocked_extensions,
        )
    )