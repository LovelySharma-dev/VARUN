from .profile import PreprocessingProfile


def load_profile(
    name: str = "default",
    version: str = "1.0",
) -> PreprocessingProfile:
    return PreprocessingProfile(
        name=name,
        version=version,
        tile_size=1024,
        overlap=128,
    )
