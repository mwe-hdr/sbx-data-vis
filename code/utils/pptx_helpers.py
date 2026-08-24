import os
import logging
from copy import deepcopy
from datetime import datetime
import shutil
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

def clone_slide(prs, slide):
    """
    Duplicate a slide.
    """

    blank_layout = prs.slide_layouts[6]

    new_slide = prs.slides.add_slide(
        blank_layout
    )

    for shape in slide.shapes:
        el = deepcopy(shape.element)
        new_slide.shapes._spTree.insert_element_before(
            el,
            "p:extLst"
        )

    return new_slide

def initialize_ppt_run():
    """
    Create dedicated PPT run folder.
    """

    base_dir = os.getcwd()

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    run_dir = os.path.join(
        base_dir,
        "data",
        "runs",
        f"ppt_run_{timestamp}"
    )

    output_dir = os.path.join(
        run_dir,
        "outputs"
    )

    os.makedirs(
        output_dir,
        exist_ok=True
    )

    return run_dir, output_dir

def get_cohort_folders(outputs_dir):

    cohorts = []

    for item in os.listdir(outputs_dir):

        full_path = os.path.join(
            outputs_dir,
            item
        )

        if os.path.isdir(full_path):
            cohorts.append(item)

    cohorts.sort()

    return cohorts

def update_cohort_text(
    slide,
    cohort_id
):

    for shape in slide.shapes:

        if (
            hasattr(shape, "name")
            and shape.name.lower()
            == "txt_cohort_id"
        ):

            if not shape.has_text_frame:
                return

            tf = shape.text_frame

            if (
                tf.paragraphs
                and tf.paragraphs[0].runs
            ):

                tf.paragraphs[0].runs[0].text = (
                    cohort_id
                )

            else:

                tf.text = cohort_id

            return

def build_powerpoint(
    run_id,
    template_file,
    output_file=None
):

    base_dir = os.getcwd()

    outputs_dir = os.path.join(
        base_dir,
        "data",
        "runs",
        run_id,
        "outputs"
    )

    if not os.path.exists(outputs_dir):
        raise FileNotFoundError(
            outputs_dir
        )

    logging.info(
        f"[ppt] Loading template: "
        f"{template_file}"
    )

    prs = Presentation(
        template_file
    )

    if len(prs.slides) == 0:
        raise ValueError(
            "Template contains no slides"
        )

    template_slide = prs.slides[0]

    cohorts = get_cohort_folders(
        outputs_dir
    )

    ppt_run_dir, ppt_output_dir = (
        initialize_ppt_run()
    )

    logging.info(
        f"[ppt] PPT run initialized: "
        f"{ppt_run_dir}"
    )

    logging.info(
        f"[ppt] Cohorts found: "
        f"{len(cohorts)}"
    )

    while len(prs.slides) > 1:
        r_id = prs.slides._sldIdLst[-1].rId
        prs.part.drop_rel(r_id)
        del prs.slides._sldIdLst[-1]

    first = True

    for cohort_id in cohorts:

        if first:
            slide = template_slide
            first = False
        else:
            slide = clone_slide(
                prs,
                template_slide
            )

        update_cohort_text(
            slide,
            cohort_id
        )

        cohort_dir = os.path.join(
            outputs_dir,
            cohort_id
        )

        populate_slide(
            slide,
            cohort_dir
        )

        logging.info(
            f"[ppt] Added slide for "
            f"{cohort_id}"
        )

        remove_unwanted_placeholders(
            slide
        )

    if output_file is None:

        output_file = os.path.join(
            ppt_output_dir,
            "powerpoint_poc.pptx"
        )

    prs.save(output_file)

    logging.info(
        f"[ppt] Saved: {output_file}"
    )

    template_snapshot = os.path.join(
        ppt_run_dir,
        os.path.basename(template_file)
    )

    shutil.copy2(
        template_file,
        template_snapshot
    )

def get_shape_by_name(
    slide,
    shape_name
):

    for shape in slide.shapes:

        if (
            hasattr(shape, "name")
            and shape.name.lower()
            == shape_name.lower()
        ):
            return shape

    return None

def get_assets(
    cohort_dir
):

    assets = {
        "vis_image": None,
        "vis_title": None,
        "vis_legend": None,
        "vis_tbl01": None,
        "vis_param": None
    }

    for filename in os.listdir(cohort_dir):

        lower = filename.lower()

        full_path = os.path.join(
            cohort_dir,
            filename
        )

        if not lower.endswith(".png"):
            continue

        if "_room_need_" in lower:
            assets["vis_tbl01"] = full_path

        if "_parameters_" in lower:
            assets["vis_param"] = full_path

        elif "_legend_" in lower:
            assets["vis_legend"] = full_path

        elif "_title_" in lower:
            assets["vis_title"] = full_path

        elif lower.startswith("vis_10__"):
            assets["vis_image"] = full_path

    return assets

def replace_picture(
    slide,
    shape_name,
    image_path
):

    if not image_path:
        logging.warning(
            f"[ppt] Missing image for "
            f"{shape_name}"
        )
        return

    shape = get_shape_by_name(
        slide,
        shape_name
    )

    if shape is None:

        logging.warning(
            f"[ppt] Placeholder not found: "
            f"{shape_name}"
        )

        return

    left = shape.left
    top = shape.top
    width = shape.width
    height = shape.height

    element = shape._element
    element.getparent().remove(
        element
    )

    slide.shapes.add_picture(
        image_path,
        left,
        top,
        width=width,
        height=height
    )

    logging.info(
        f"[ppt] Replaced "
        f"{shape_name}"
    )

    new_pic = slide.shapes.add_picture(
        image_path,
        left,
        top,
        width=width,
        height=height
    )

    new_pic.name = shape_name

def populate_slide(
    slide,
    cohort_dir
):

    assets = get_assets(
        cohort_dir
    )

    replace_picture(
        slide,
        "vis_image",
        assets["vis_image"]
    )

    replace_picture(
        slide,
        "vis_title",
        assets["vis_title"]
    )

    replace_picture(
        slide,
        "vis_legend",
        assets["vis_legend"]
    )

    replace_picture(
        slide,
        "vis_tbl01",
        assets["vis_tbl01"]
    )

    replace_picture(
        slide,
        "vis_param",
        assets["vis_param"]
    )

def remove_unwanted_placeholders(slide):

    remove_prefixes = [
        "title",
        "text placeholder"
    ]

    remove_names = [
        "picture 58",
        "picture 48"
    ]

    shapes_to_remove = []

    for shape in slide.shapes:

        name = str(
            getattr(shape, "name", "")
        ).lower()

        if (
            any(name.startswith(p) for p in remove_prefixes)
            or name in remove_names
        ):
            shapes_to_remove.append(
                shape
            )

    for shape in shapes_to_remove:

        element = shape._element

        element.getparent().remove(
            element
        )

        logging.info(
            f"[ppt] Removed "
            f"{shape.name}"
        )




