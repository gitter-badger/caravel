"""
The photos module manages the uploading, resizing, and serving of pictures.
"""

import time, uuid, os, logging, re, cloudstorage
from google.appengine.api import images

from caravel import app

PHOTO_LIFETIME = 60 * 24 * 60 * 60 # 60 days
GCS_BUCKET = "hosted-caravel.appspot.com"
SIZES = {'small': (300, 300, True), 'large': (600, 600, False)}

def collect_garbage():
    """
    Removes all uploaded photos that should have since expired.
    """

    for photo in cloudstorage.listbucket("/" + GCS_BUCKET):
        should_delete = False
        try:
            posted_at, _ = photo.filename.split("/")[2].split("-", 1)
            posted_at = int(posted_at)
            if (time.time() - posted_at) > PHOTO_LIFETIME:
                should_delete = True
        except ValueError, exc:
            should_delete = True
            logging.exception(exc)

        if should_delete:
            try:
                cloudstorage.delete(photo.filename)
            except cloudstorage.NotFoundError:
                pass # ignore concurrent removals.

def upload(file_object, size='medium'):
    """
    Uploads the given photo, returning a dict mapping from size name to a URL.
    """

    now = int(time.time())
    guid = uuid.uuid4()

    max_width, max_height, crop_to_fit = SIZES.get(size, (None, None, False))

    # Resize image to fit in the given size, and re-encode as JPEG.
    img = images.Image(file_object.read())
    if max_width and max_height:
        img.resize(max_width, max_height, crop_to_fit=crop_to_fit)
    img.im_feeling_lucky()
    result_data = img.execute_transforms(output_encoding=images.JPEG)

    # Save the image to GCS.
    photo_id = "{}-{}-{}".format(now, guid, size)
    output_file = cloudstorage.open(
        filename="/{}/{}".format(GCS_BUCKET, photo_id),
        mode="w",
        content_type="image/jpg",
        options={"x-goog-acl": "public-read"}
    )
    output_file.write(result_data)
    output_file.close()

    return photo_id

@app.template_filter("public_url")
def public_url(path):
    """
    Returns a complete file URL given its path.
    """

    if not path or not re.match(r'^[a-zA-Z0-9\-]+$', path):
        if path:
            raise ValueError("Invalid path {!r}".format(path))
        return ""

    path = GCS_BUCKET + "/" + path
    if os.environ["SERVER_SOFTWARE"].startswith("Development/"):
        return "/_ah/gcs/" + path
    else:
        return "https://storage.googleapis.com/" + path
