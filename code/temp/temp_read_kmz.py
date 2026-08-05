from lxml import etree
from shapely.geometry import Polygon
import pandas as pd

KML_FILE = r"C:\lwf\sbx-data-vis\data\input\geo\cohort_locations\ecu_locations.kml"
OUTPUT_CSV = r"C:\lwf\sbx-data-vis\data\input\geo\cohort_locations\ecu_locations_all.csv"

NS = {
    "kml": "http://www.opengis.net/kml/2.2"
}


def parse_coordinates(coord_text):
    coords = []

    if not coord_text:
        return coords

    for row in coord_text.strip().split():

        parts = row.split(",")

        if len(parts) >= 2:
            lon = float(parts[0])
            lat = float(parts[1])

            coords.append((lon, lat))

    return coords


def polygon_centroid(coords):
    try:

        poly = Polygon(coords)

        if poly.is_valid:
            c = poly.centroid
            return c.y, c.x

    except Exception:
        pass

    return None, None


def process_placemark(placemark, category, rows):

    name_node = placemark.find(
        "kml:name",
        namespaces=NS
    )

    name = ""

    if name_node is not None and name_node.text:
        name = name_node.text.strip()

    # -------------------------
    # POINTS
    # -------------------------

    point_nodes = placemark.xpath(
        ".//kml:Point/kml:coordinates",
        namespaces=NS
    )

    for point in point_nodes:

        coords = parse_coordinates(point.text)

        if not coords:
            continue

        lon, lat = coords[0]

        rows.append({
            "category": category,
            "name": name,
            "geometry_type": "Point",
            "latitude": lat,
            "longitude": lon,
            "vertex_count": 1,
            "polygon_coordinates": ""
        })

    # -------------------------
    # POLYGONS
    # -------------------------

    polygon_nodes = placemark.xpath(
        ".//kml:Polygon//kml:coordinates",
        namespaces=NS
    )

    for poly in polygon_nodes:

        coords = parse_coordinates(poly.text)

        if len(coords) < 3:
            continue

        centroid_lat, centroid_lon = polygon_centroid(coords)

        coord_string = "; ".join(
            f"{lat},{lon}"
            for lon, lat in coords
        )

        rows.append({
            "category": category,
            "name": name,
            "geometry_type": "Polygon",
            "latitude": centroid_lat,
            "longitude": centroid_lon,
            "vertex_count": len(coords),
            "polygon_coordinates": coord_string
        })


def process_folder(folder, parent_category, rows):

    folder_name_node = folder.find(
        "kml:name",
        namespaces=NS
    )

    category = parent_category

    if (
        folder_name_node is not None
        and folder_name_node.text
    ):
        category = folder_name_node.text.strip()

    placemarks = folder.xpath(
        "./kml:Placemark",
        namespaces=NS
    )

    for placemark in placemarks:
        process_placemark(
            placemark,
            category,
            rows
        )

    child_folders = folder.xpath(
        "./kml:Folder",
        namespaces=NS
    )

    for child in child_folders:
        process_folder(
            child,
            category,
            rows
        )


def main():

    parser = etree.XMLParser(recover=True)
    tree = etree.parse(KML_FILE, parser)

    rows = []

    folders = tree.xpath(
        "//kml:Folder",
        namespaces=NS
    )

    for folder in folders:
        process_folder(
            folder,
            "",
            rows
        )

    df = pd.DataFrame(rows)

    df.to_csv(
        OUTPUT_CSV,
        index=False
    )

    print(df.head())
    print()
    print(f"Exported {len(df)} records")
    print(f"Output: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()