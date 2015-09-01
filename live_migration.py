from google.appengine.api import mail
import re, traceback, json, urllib2, datetime, time

import models
import search

def pull_from_listing(permalink):
    """
    Retrieves the listing from the old Marketplace, and save it to the database.
    """

    # Retrieve existing listing by the permalink.
    if not re.match(r"^[a-zA-Z\-0-9]+$", permalink):
        raise ValueError("Invalid permalink: {!r}".format(permalink))
    url = "http://marketplace.uchicago.edu/{}".format(permalink)
    data = urllib2.urlopen(url + ".json").read()
    if not data:
        return

    json_data = json.loads(data)

    # Parse the listing date from not-quite-ISO8601 to App Engine UTC.
    posting_time = time.mktime((datetime.datetime.strptime(
        json_data["renewed_at"][:-6], "%Y-%m-%dT%H:%M:%S"
    ) - datetime.timedelta(
        hours=float(json_data["renewed_at"][-6:-3]),
        minutes=float(json_data["renewed_at"][-2:])
    )).timetuple())

    # (Idempotently) save this entity into the datastore.
    models.Listing(
        key_name=json_data["permalink"],
        seller=json_data["seller"]["email"],
        posting_time=posting_time,
        description=re.sub(r'(<a.*>\n*)', '', json_data["description"].replace("<p>", "").replace("</p>", ""))
        .replace,
        details=json_data["details"],
        price=(int(float(json_data["price"]) * 100))
    ).put()
    
    # Invalidate the cache.
    search.invalidate_listing(json_data["permalink"])