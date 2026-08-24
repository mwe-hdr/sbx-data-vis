import pandas as pd
import re
from rapidfuzz import fuzz

# =====================================================
# LOAD DATA
# =====================================================

with open(f"C:\lwf\sbx-data-vis\data\input\ecu_clinic_encounter_names.csv") as f:
    list1 = [x.strip() for x in f if x.strip()]

with open(f"C:\lwf\sbx-data-vis\data\input\ecu_clinic_property_names.csv") as f:
    list2 = [x.strip() for x in f if x.strip()]

# =====================================================
# NORMALIZATION
# =====================================================

ABBREVIATIONS = {
    "HEM/ONC": "HEMATOLOGY ONCOLOGY",
    "HEM ONC": "HEMATOLOGY ONCOLOGY",
    "FM": "FAMILY MEDICINE",
    "PT": "PHYSICAL THERAPY",
    "OT": "OCCUPATIONAL THERAPY",
    "OBGYN": "WOMENS CARE",
    "OB/GYN": "WOMENS CARE",
    "U/S": "ULTRASOUND",
    "IM": "INTERNAL MEDICINE",
}

REMOVE_WORDS = [
    "ECU HEALTH",
    "VIDANT",
    "COMM",
    "ACAD",
    "OBMG",
    "OBH",
    "EMC",
    "BFT",
    "BER",
    "CHO",
    "NOR",
    "RCH",
    "ZZ",
    "FORMERLY"
]

KNOWN_LOCATIONS = [
    "GREENVILLE",
    "WASHINGTON",
    "TARBORO",
    "WILSON",
    "EDENTON",
    "AHOSKIE",
    "RICHLANDS",
    "LA GRANGE",
    "PINK HILL",
    "PINETOPS",
    "BELHAVEN",
    "KENANSVILLE",
    "ROANOKE RAPIDS",
    "KINSTON",
    "WALLACE",
    "HERTFORD",
    "CHOCOWINITY",
    "WINDSOR",
    "PLYMOUTH",
    "COLUMBIA",
    "WILLIAMSTON",
    "NAGS HEAD",
    "KITTY HAWK",
    "MANTEO",
    "AVON",
    "OUTER BANKS",
]

def normalize(text):

    text = text.upper()

    for old, new in ABBREVIATIONS.items():
        text = text.replace(old, new)

    for word in REMOVE_WORDS:
        text = text.replace(word, " ")

    text = re.sub(r"[-_/]", " ", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def extract_location(text):

    txt = text.upper()

    for loc in sorted(
        KNOWN_LOCATIONS,
        key=len,
        reverse=True
    ):
        if loc in txt:
            return loc

    return ""


def confidence_bucket(score):

    if score >= 90:
        return "HIGH"

    if score >= 75:
        return "REVIEW"

    return "LOW"


# =====================================================
# MATCH SCORE
# =====================================================

def calculate_score(source, target):

    source_norm = normalize(source)
    target_norm = normalize(target)

    source_loc = extract_location(source)
    target_loc = extract_location(target)

    token_score = fuzz.token_set_ratio(
        source_norm,
        target_norm
    )

    sort_score = fuzz.token_sort_ratio(
        source_norm,
        target_norm
    )

    partial_score = fuzz.partial_ratio(
        source_norm,
        target_norm
    )

    name_score = (
        token_score * 0.50
        + sort_score * 0.30
        + partial_score * 0.20
    )

    # Location weighting
    if source_loc and target_loc:

        if source_loc == target_loc:
            location_score = 100

        else:
            location_score = fuzz.ratio(
                source_loc,
                target_loc
            )
    else:
        location_score = 50

    total_score = (
        name_score * 0.75
        + location_score * 0.25
    )

    return round(total_score, 2)


# =====================================================
# GENERIC MATCH FUNCTION
# =====================================================

def generate_matches(source_list, target_list,
                     source_name, target_name,
                     top_n=3):

    rows = []

    for source in source_list:

        scores = []

        for target in target_list:

            score = calculate_score(
                source,
                target
            )

            scores.append((target, score))

        scores = sorted(
            scores,
            key=lambda x: x[1],
            reverse=True
        )

        best_target, best_score = scores[0]

        row = {
            source_name: source,
            f"Best_{target_name}": best_target,
            "Best_Score": best_score,
            "Confidence": confidence_bucket(best_score)
        }

        for i in range(top_n):
            tgt, sc = scores[i]

            row[f"Candidate_{i+1}"] = tgt
            row[f"Candidate_{i+1}_Score"] = sc

        rows.append(row)

    return pd.DataFrame(rows)


# =====================================================
# RUN BOTH DIRECTIONS
# =====================================================

list1_to_list2 = generate_matches(
    list1,
    list2,
    "List1",
    "List2"
)

list2_to_list1 = generate_matches(
    list2,
    list1,
    "List2",
    "List1"
)

# =====================================================
# FIND RECIPROCAL MATCHES
# =====================================================

reciprocal = []

for _, row1 in list1_to_list2.iterrows():

    source = row1["List1"]
    target = row1["Best_List2"]

    reverse_rows = list2_to_list1[
        list2_to_list1["List2"] == target
    ]

    if len(reverse_rows) == 0:
        continue

    reverse_best = reverse_rows.iloc[0]["Best_List1"]

    reciprocal.append({
        "List1": source,
        "Best_List2": target,
        "Score": row1["Best_Score"],
        "Reciprocal_Match":
            source == reverse_best
    })

reciprocal_df = pd.DataFrame(reciprocal)

# =====================================================
# EXPORT
# =====================================================

with pd.ExcelWriter(
    f"C:\lwf\sbx-data-vis\data\input\ecu_clinic_matches.xlsx",
    engine="openpyxl"
) as writer:

    list1_to_list2.to_excel(
        writer,
        sheet_name="List1_to_List2",
        index=False
    )

    list2_to_list1.to_excel(
        writer,
        sheet_name="List2_to_List1",
        index=False
    )

    reciprocal_df.to_excel(
        writer,
        sheet_name="Reciprocal_Check",
        index=False
    )

print("Finished.")