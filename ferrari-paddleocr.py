#!/usr/bin/env python3
"""
Ferrari callout detector + PaddleOCR recognition-only batch.

Usage:
    ./ferrari_paddle_recognition.py
    ./ferrari_paddle_recognition.py BLACKNESS_THRESHOLD WHITENESS_THRESHOLD
    ./ferrari_paddle_recognition.py --help

Pipeline:
    detect -> trim -> accumulate -> padded targets
    -> build single-column sprite for inspection only
    -> ONE TextRecognition.predict([...all padded crops...]) call
    -> overlay -> JSON

There is NO Paddle text-detection stage. We already know every target box.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import cv2
import numpy as np

SOURCE_IMAGE = Path("test/360-modena_001.jpg")

OUTPUT_TRIMMED = Path("../ferrari-nla/360-modena_001.trimmed.png")
OUTPUT_TARGETS = Path("../ferrari-nla/360-modena_001.targets.png")
OUTPUT_SPRITE = Path("../ferrari-nla/360-modena_001.sprite.png")
OUTPUT_OCR = Path("../ferrari-nla/360-modena_001.ocr.png")
OUTPUT_JSON = Path("../ferrari-nla/360-modena_001.targets.json")

GLYPH_H = 11
SCAN_WIDTHS = (5, 7, 12, 14, 15, 18, 19, 22)
SCAN_BORDER = 2

DEFAULT_BLACKNESS_MAX = 180
DEFAULT_WHITENESS_MIN = 250

TRIM_H = 14
TRIM_WHITE = 220.0

CLICK_PAD_Y = 2
CLICK_PAD_X = 3
CLICK_PAD_X_NARROW = 4
NARROW_SINGLE_MAX_W = 8

SPRITE_CELL_W = 40
SPRITE_CELL_H = 20

PADDLE_REC_MODEL = "en_PP-OCRv5_mobile_rec"

OCR_FONT = cv2.FONT_HERSHEY_SIMPLEX
OCR_FONT_SCALE = 0.36
OCR_FONT_THICKNESS = 1
OCR_BOX_PAD = 1


def usage(exit_code: int = 0) -> int:
    name = Path(sys.argv[0]).name
    out = sys.stdout if exit_code == 0 else sys.stderr
    print(
        f"Usage: {name} [BLACKNESS_THRESHOLD WHITENESS_THRESHOLD]\n"
        f"       {name} --help\n\n"
        f"Defaults:\n"
        f"  BLACKNESS_THRESHOLD = {DEFAULT_BLACKNESS_MAX}\n"
        f"  WHITENESS_THRESHOLD = {DEFAULT_WHITENESS_MIN}\n",
        file=out,
    )
    return exit_code


def parse_thresholds() -> tuple[int, int]:
    args = sys.argv[1:]
    if any(a in ("-h", "--help") for a in args):
        raise SystemExit(usage(0))
    if not args:
        return DEFAULT_BLACKNESS_MAX, DEFAULT_WHITENESS_MIN
    if len(args) != 2:
        raise ValueError("expected zero arguments or exactly two integer thresholds")
    try:
        blackness = int(args[0])
        whiteness = int(args[1])
    except ValueError:
        raise ValueError("thresholds must be integers")
    if not 0 <= blackness <= 255:
        raise ValueError("BLACKNESS_THRESHOLD must be 0..255")
    if not 0 <= whiteness <= 255:
        raise ValueError("WHITENESS_THRESHOLD must be 0..255")
    return blackness, whiteness


def integral_image(gray: np.ndarray) -> np.ndarray:
    v = gray.astype(np.float64)
    return np.pad(v.cumsum(0).cumsum(1), ((1, 0), (1, 0)), mode="constant")


def rect_sum_map(ii: np.ndarray, h: int, w: int) -> np.ndarray:
    return ii[h:, w:] - ii[:-h, w:] - ii[h:, :-w] + ii[:-h, :-w]


def scan_width(
    gray: np.ndarray,
    ii: np.ndarray,
    width: int,
    blackness_threshold: int,
    whiteness_threshold: int,
) -> list[dict]:
    H, W = gray.shape
    outer_h = GLYPH_H + 2 * SCAN_BORDER
    outer_w = width + 2 * SCAN_BORDER
    scan_h = H - GLYPH_H - 2 * SCAN_BORDER + 1
    scan_w = W - width - 2 * SCAN_BORDER + 1
    if scan_h <= 0 or scan_w <= 0:
        return []

    centre_all = rect_sum_map(ii, GLYPH_H, width)
    outer_all = rect_sum_map(ii, outer_h, outer_w)
    centre = centre_all[
        SCAN_BORDER:SCAN_BORDER + scan_h,
        SCAN_BORDER:SCAN_BORDER + scan_w,
    ]
    outer = outer_all[:scan_h, :scan_w]

    centre_area = float(GLYPH_H * width)
    ring_area = float(outer_h * outer_w) - centre_area
    centre_mean = centre / centre_area
    ring_mean = (outer - centre) / ring_area

    passed = (
        (centre_mean <= blackness_threshold)
        & (ring_mean >= whiteness_threshold)
    )
    ys, xs = np.where(passed)

    return [
        {
            "x": int(x + SCAN_BORDER),
            "y": int(y + SCAN_BORDER),
            "w": int(width),
            "h": GLYPH_H,
            "centre_greyscale": round(float(centre_mean[y, x]), 2),
            "whiteness": round(float(ring_mean[y, x]), 2),
        }
        for y, x in zip(ys, xs)
    ]


def trim_box(gray: np.ndarray, box: dict) -> dict | None:
    H, W = gray.shape
    left = int(box["x"])
    right = int(box["x"] + box["w"])
    cy = box["y"] + box["h"] / 2.0
    y1 = int(round(cy - TRIM_H / 2.0))
    y1 = max(0, min(H - TRIM_H, y1))
    y2 = y1 + TRIM_H
    left = max(0, left)
    right = min(W, right)

    while left < right:
        if float(gray[y1:y2, left:left + 1].mean()) < TRIM_WHITE:
            break
        left += 1

    while right > left:
        if float(gray[y1:y2, right - 1:right].mean()) < TRIM_WHITE:
            break
        right -= 1

    if right <= left:
        return None

    return {"x": left, "y": y1, "w": right - left, "h": TRIM_H}


def accumulate_trimmed(shape: tuple[int, int], boxes: list[dict]) -> np.ndarray:
    H, W = shape
    mask = np.zeros((H, W), dtype=np.uint8)
    for b in boxes:
        x1, y1 = b["x"], b["y"]
        x2 = min(W, x1 + b["w"])
        y2 = min(H, y1 + b["h"])
        mask[y1:y2, x1:x2] = 255
    return mask


def connected_regions(mask: np.ndarray) -> list[dict]:
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    out = []
    for i in range(1, count):
        x, y, w, h, area = stats[i]
        out.append({"x": int(x), "y": int(y), "w": int(w), "h": int(h), "area": int(area)})
    out.sort(key=lambda b: (b["y"], b["x"]))
    return out


def add_click_padding(box: dict, shape: tuple[int, int]) -> dict:
    H, W = shape
    pad_x = CLICK_PAD_X_NARROW if box["w"] <= NARROW_SINGLE_MAX_W else CLICK_PAD_X
    x1 = max(0, box["x"] - pad_x)
    y1 = max(0, box["y"] - CLICK_PAD_Y)
    x2 = min(W, box["x"] + box["w"] + pad_x)
    y2 = min(H, box["y"] + box["h"] + CLICK_PAD_Y)
    return {
        "x": x1,
        "y": y1,
        "w": x2 - x1,
        "h": y2 - y1,
        "pad_x": pad_x,
        "pad_y": CLICK_PAD_Y,
        "tight_box": {"x": box["x"], "y": box["y"], "w": box["w"], "h": box["h"]},
    }


def render_trimmed(source_path: Path, boxes: list[dict], output_path: Path) -> None:
    image = cv2.imread(str(source_path), cv2.IMREAD_COLOR)
    for b in boxes:
        cv2.rectangle(
            image,
            (b["x"], b["y"]),
            (b["x"] + b["w"] - 1, b["y"] + b["h"] - 1),
            (255, 80, 0),
            1,
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), image)


def render_targets(source_path: Path, targets: list[dict], output_path: Path) -> None:
    image = cv2.imread(str(source_path), cv2.IMREAD_COLOR)
    overlay = image.copy()
    for b in targets:
        cv2.rectangle(
            overlay,
            (b["x"], b["y"]),
            (b["x"] + b["w"] - 1, b["y"] + b["h"] - 1),
            (0, 220, 0),
            -1,
        )
    image = cv2.addWeighted(overlay, 0.40, image, 0.60, 0)
    cv2.imwrite(str(output_path), image)


def build_crops_and_sprite(
    gray: np.ndarray,
    targets: list[dict],
) -> tuple[list[np.ndarray], np.ndarray, list[dict]]:
    """Create the exact padded OCR crops plus a single-column diagnostic sprite."""
    crops: list[np.ndarray] = []
    sprite = np.full((max(1, len(targets)) * SPRITE_CELL_H, SPRITE_CELL_W), 255, dtype=np.uint8)
    mapping = []

    for index, target in enumerate(targets):
        crop_gray = gray[
            target["y"]:target["y"] + target["h"],
            target["x"]:target["x"] + target["w"],
        ].copy()

        # Paddle TextRecognition expects H x W x C, not 2-D grayscale.
        # Keep the sprite grayscale, but feed Paddle contiguous BGR arrays.
        crop_bgr = cv2.cvtColor(crop_gray, cv2.COLOR_GRAY2BGR)
        crop_bgr = np.ascontiguousarray(crop_bgr, dtype=np.uint8)
        crops.append(crop_bgr)

        ch, cw = crop_gray.shape
        row_y = index * SPRITE_CELL_H
        paste_x = max(0, (SPRITE_CELL_W - cw) // 2)
        paste_y = row_y + max(0, (SPRITE_CELL_H - ch) // 2)

        draw_crop = crop_gray
        if cw > SPRITE_CELL_W:
            draw_crop = draw_crop[:, :SPRITE_CELL_W]
            ch, cw = draw_crop.shape
            paste_x = 0
        if ch > SPRITE_CELL_H:
            draw_crop = draw_crop[:SPRITE_CELL_H, :]
            ch, cw = draw_crop.shape
            paste_y = row_y

        sprite[paste_y:paste_y + ch, paste_x:paste_x + cw] = draw_crop

        mapping.append({
            "index": index,
            "row": index,
            "cell": {"x": 0, "y": row_y, "w": SPRITE_CELL_W, "h": SPRITE_CELL_H},
            "target_box": target,
            "tight_box": target["tight_box"],
        })

    return crops, sprite, mapping


def result_payload(result) -> dict:
    data = getattr(result, "json", None)
    if callable(data):
        data = data()
    if data is None:
        to_dict = getattr(result, "to_dict", None)
        if callable(to_dict):
            data = to_dict()
    if isinstance(data, str):
        data = json.loads(data)
    if not isinstance(data, dict):
        raise RuntimeError(f"unexpected TextRecognition result type: {type(data)!r}")
    return data.get("res", data)


def run_paddle_recognition_once(crops: list[np.ndarray]) -> list[dict]:
    """One recognition-only predict() call. No text detector."""
    os.environ["FLAGS_use_mkldnn"] = "0"
    os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

    try:
        from paddleocr import TextRecognition
    except ImportError as exc:
        raise RuntimeError(
            "PaddleOCR is not installed. Install with:\n"
            "  python3 -m pip install paddleocr paddlepaddle"
        ) from exc

    try:
        model = TextRecognition(
            model_name=PADDLE_REC_MODEL,
            device="cpu",
            enable_mkldnn=False,
        )

        # ONE call. Paddle batches the known target crops internally.
        output = model.predict(
            input=crops,
            batch_size=max(1, len(crops)),
        )
    except Exception as exc:
        raise RuntimeError(f"Paddle TextRecognition failed: {exc}") from exc

    results = []
    for index, result in enumerate(output):
        payload = result_payload(result)
        raw = str(payload.get("rec_text", "")).strip()
        score = float(payload.get("rec_score", -1.0))
        digits = "".join(ch for ch in raw if ch.isdigit())
        results.append({
            "index": index,
            "raw_text": raw,
            "digits": digits,
            "score": score,
        })

    return results


def expected_digits(tight_width: int) -> int:
    if tight_width <= 8:
        return 1
    if tight_width <= 16:
        return 2
    return 3


def resolve_ocr(rec_results: list[dict], targets: list[dict]) -> list[dict]:
    by_index = {r["index"]: r for r in rec_results}
    results = []

    for index, target in enumerate(targets):
        rec = by_index.get(index, {"raw_text": "", "digits": "", "score": -1.0})
        digits = rec["digits"]
        n_expected = expected_digits(target["tight_box"]["w"])
        accepted = digits.isdigit() and len(digits) == n_expected

        results.append({
            "index": index,
            "tight_box": target["tight_box"],
            "target_box": target,
            "expected_digits": n_expected,
            "ocr_raw": rec["raw_text"],
            "ocr_text": digits if accepted else "",
            "ocr_accepted": accepted,
            "ocr_conf": round(float(rec["score"]), 4),
        })

    return results


def render_ocr_overlay(
    source_path: Path,
    targets: list[dict],
    ocr_items: list[dict],
    output_path: Path,
) -> None:
    image = cv2.imread(str(source_path), cv2.IMREAD_COLOR)
    overlay = image.copy()

    for b in targets:
        cv2.rectangle(
            overlay,
            (b["x"], b["y"]),
            (b["x"] + b["w"] - 1, b["y"] + b["h"] - 1),
            (0, 220, 0),
            -1,
        )
    image = cv2.addWeighted(overlay, 0.18, image, 0.82, 0)

    BLUE = (255, 80, 0)
    RED = (0, 0, 220)
    WHITE = (255, 255, 255)

    for item in ocr_items:
        tb = item["tight_box"]
        x = int(tb["x"] + tb["w"])
        y = int(tb["y"] + tb["h"])

        if item["ocr_accepted"]:
            text = item["ocr_text"]
            (tw, th), baseline = cv2.getTextSize(
                text,
                OCR_FONT,
                OCR_FONT_SCALE,
                OCR_FONT_THICKNESS,
            )
            box_w = tw + 2 * OCR_BOX_PAD
            box_h = th + baseline + 2 * OCR_BOX_PAD
            cv2.rectangle(image, (x, y), (x + box_w - 1, y + box_h - 1), WHITE, -1)
            cv2.rectangle(image, (x, y), (x + box_w - 1, y + box_h - 1), BLUE, 1)
            cv2.putText(
                image,
                text,
                (x + OCR_BOX_PAD, y + OCR_BOX_PAD + th),
                OCR_FONT,
                OCR_FONT_SCALE,
                BLUE,
                OCR_FONT_THICKNESS,
                cv2.LINE_AA,
            )
            item["diagnostic_box"] = {"x": x, "y": y, "w": box_w, "h": box_h}
        else:
            cv2.putText(
                image,
                "X",
                (x, y + 10),
                OCR_FONT,
                OCR_FONT_SCALE,
                RED,
                OCR_FONT_THICKNESS,
                cv2.LINE_AA,
            )
            item["diagnostic_box"] = None

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), image)


def main() -> int:
    try:
        blackness, whiteness = parse_thresholds()
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return usage(2)

    source = SOURCE_IMAGE.resolve()
    gray = cv2.imread(str(source), cv2.IMREAD_GRAYSCALE)
    if gray is None:
        print(f"ERROR: cannot read image: {source}", file=sys.stderr)
        return 2

    H, W = gray.shape
    ii = integral_image(gray)

    raw_candidates = []
    trimmed_candidates = []
    per_width = {}

    for width in SCAN_WIDTHS:
        raw = scan_width(gray, ii, width, blackness, whiteness)
        trimmed = []
        for candidate in raw:
            box = trim_box(gray, candidate)
            if box is not None:
                trimmed.append(box)
                trimmed_candidates.append(box)
        raw_candidates.extend(raw)
        per_width[str(width)] = {"raw": len(raw), "trimmed": len(trimmed)}
        print(f"Width {width:2d}: {len(raw):6d} raw  {len(trimmed):6d} trimmed")

    mask = accumulate_trimmed((H, W), trimmed_candidates)
    tight_boxes = connected_regions(mask)
    targets = [add_click_padding(box, (H, W)) for box in tight_boxes]

    output_trimmed = OUTPUT_TRIMMED.resolve()
    output_targets = OUTPUT_TARGETS.resolve()
    output_sprite = OUTPUT_SPRITE.resolve()
    output_ocr = OUTPUT_OCR.resolve()
    output_json = OUTPUT_JSON.resolve()

    render_trimmed(source, tight_boxes, output_trimmed)
    render_targets(source, targets, output_targets)

    crops, sprite, sprite_mapping = build_crops_and_sprite(gray, targets)
    output_sprite.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_sprite), sprite)

    print(f"Targets found:      {len(targets)}")

    try:
        rec_results = run_paddle_recognition_once(crops)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    ocr_items = resolve_ocr(rec_results, targets)
    render_ocr_overlay(source, targets, ocr_items, output_ocr)

    accepted = sum(1 for x in ocr_items if x["ocr_accepted"])
    rejected = len(ocr_items) - accepted

    payload = {
        "source_image": str(source),
        "source_width": W,
        "source_height": H,
        "blackness_threshold": blackness,
        "whiteness_threshold": whiteness,
        "trim_height": TRIM_H,
        "trim_white_threshold": TRIM_WHITE,
        "click_padding": {
            "vertical": CLICK_PAD_Y,
            "horizontal_default": CLICK_PAD_X,
            "horizontal_narrow": CLICK_PAD_X_NARROW,
            "narrow_single_max_width": NARROW_SINGLE_MAX_W,
        },
        "ocr": {
            "engine": "PaddleOCR TextRecognition only",
            "model": PADDLE_REC_MODEL,
            "batch_size": len(crops),
            "detection_stage": False,
        },
        "sprite": {
            "diagnostic_only": True,
            "single_column": True,
            "cell_width": SPRITE_CELL_W,
            "cell_height": SPRITE_CELL_H,
            "rows": len(targets),
            "image": str(output_sprite),
            "mapping": sprite_mapping,
        },
        "raw_candidate_count": len(raw_candidates),
        "trimmed_candidate_count": len(trimmed_candidates),
        "candidate_count_by_width": per_width,
        "tight_box_count": len(tight_boxes),
        "target_count": len(targets),
        "ocr_accepted_count": accepted,
        "ocr_rejected_count": rejected,
        "tight_boxes": tight_boxes,
        "targets": targets,
        "ocr_items": ocr_items,
        "ocr_overlay": str(output_ocr),
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print()
    print(f"{source.name}: {len(targets)} boxes, {accepted} OCR matches, {rejected} non-matches")
    print()
    print(f"Trimmed: {output_trimmed}")
    print(f"Sprite:  {output_sprite}")
    print(f"Targets: {output_targets}")
    print(f"OCR:     {output_ocr}")
    print(f"JSON:    {output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

