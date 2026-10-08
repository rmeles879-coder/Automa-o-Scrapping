"""Respostas sintéticas baseadas nos formatos públicos das APIs de assets."""

from video_production.config import Settings

# Valores artificiais exclusivos de testes; não são credenciais reais.
PIXABAY_TEST_KEY = "not-a-real-pixabay-key"
UNSPLASH_TEST_KEY = "not-a-real-unsplash-key"


def config():
    return Settings(_env_file=None, pixabay_api_key=None, unsplash_access_key=None)


def pixabay_image(asset_id=101):
    return {
        "id": asset_id,
        "type": "photo",
        "tags": "forest, nature, forest",
        "previewURL": "https://cdn.pixabay.com/photo/forest-small.jpg",
        "largeImageURL": "https://cdn.pixabay.com/photo/forest.jpg",
        "pageURL": "https://pixabay.com/photos/forest-101/",
        "user": "Example Photographer",
        "imageWidth": 4000,
        "imageHeight": 3000,
    }


def pixabay_video():
    return {
        "id": 202,
        "tags": "forest, trees",
        "duration": 12,
        "pageURL": "https://pixabay.com/videos/forest-202/",
        "user": "Example Filmmaker",
        "videos": {
            "large": {
                "url": "https://videos.pixabay.com/video/forest-large.mp4",
                "width": 1920,
                "height": 1080,
                "thumbnail": "https://cdn.pixabay.com/video/forest.jpg",
            },
            "small": {
                "url": "https://videos.pixabay.com/video/forest-small.mp4",
                "width": 640,
                "height": 360,
            },
        },
    }


def unsplash_photo(asset_id="photo-1"):
    return {
        "id": asset_id,
        "width": 6000,
        "height": 4000,
        "description": None,
        "alt_description": "Forest at sunrise",
        "tags": [{"title": "forest"}, {"title": "nature"}, {"title": "forest"}],
        "urls": {
            "full": f"https://images.unsplash.com/{asset_id}?ixid=example",
            "thumb": f"https://images.unsplash.com/{asset_id}?w=200",
        },
        "links": {
            "html": f"https://unsplash.com/photos/{asset_id}",
            "download_location": f"https://api.unsplash.com/photos/{asset_id}/download?ixid=test",
        },
        "user": {"name": "Example Photographer", "username": "example"},
    }


def commons_page(asset_id=303, *, mime="image/jpeg", index=1):
    return {
        "pageid": asset_id,
        "ns": 6,
        "title": "File:Forest.jpg",
        "index": index,
        "imageinfo": [
            {
                "url": "https://upload.wikimedia.org/wikipedia/commons/a/ab/Forest.jpg",
                "descriptionurl": "https://commons.wikimedia.org/wiki/File:Forest.jpg",
                "thumburl": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Forest.jpg",
                "width": 3200,
                "height": 2400,
                "mime": mime,
                "extmetadata": {
                    "ObjectName": {"value": "<span>Forest &amp; trees</span>"},
                    "ImageDescription": {"value": "<p>Morning</p><p>in the forest.</p>"},
                    "Artist": {"value": '<a href="https://example.org">Example Author</a>'},
                    "Credit": {"value": "Own work"},
                    "LicenseShortName": {"value": "CC BY-SA 4.0"},
                    "LicenseUrl": {"value": "//creativecommons.org/licenses/by-sa/4.0/"},
                    "Categories": {"value": "Forests|Nature|Forests"},
                },
            }
        ],
    }
