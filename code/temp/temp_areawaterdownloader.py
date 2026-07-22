import os
import requests
from io import BytesIO
from zipfile import ZipFile

OUTPUT_DIR = r"C:\lwf\sbx-data-vis\data\input\geo\tl_2025_water"

GEOIDS = [
    "37029",
    "37053",
    "37073",
    "37091",
    "37131",
    "51001",
    "51036",
    "51041",
    "51053",
    "51073",
    "51081",
    "51087",
    "51093",
    "51095",
    "51097",
    "51115",
    "51119",
    "51127",
    "51131",
    "51149",
    "51175",
    "51181",
    "51183",
    "51199",
    "51550",
    "51620",
    "51650",
    "51670",
    "51700",
    "51710",
    "51730",
    "51735",
    "51740",
    "51800",
    "51810",
    "51830"
]

BASE_URL = (
    "https://www2.census.gov/geo/tiger/"
    "TIGER2025/AREAWATER"
)

os.makedirs(
    OUTPUT_DIR,
    exist_ok=True
)

print(
    f"\nDownloading and extracting "
    f"{len(GEOIDS)} water layers...\n"
)

for geoid in GEOIDS:

    shp_file = os.path.join(
        OUTPUT_DIR,
        f"tl_2025_{geoid}_areawater.shp"
    )

    if os.path.exists(shp_file):

        print(
            f"SKIP  {geoid} (already exists)"
        )

        continue

    filename = (
        f"tl_2025_{geoid}_areawater.zip"
    )

    url = (
        f"{BASE_URL}/{filename}"
    )

    try:

        print(
            f"GET   {filename}"
        )

        response = requests.get(
            url,
            timeout=120
        )

        response.raise_for_status()

        with ZipFile(
            BytesIO(response.content)
        ) as zf:

            for member in zf.namelist():

                zf.extract(
                    member,
                    OUTPUT_DIR
                )

        print(
            f"OK    {geoid}"
        )

    except Exception as ex:

        print(
            f"FAIL  {geoid}: {ex}"
        )

print("\nDone.")