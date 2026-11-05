#!/usr/bin/env python3

import os
import shutil
import glob
import numpy as np
from PIL import Image

# Parameters
THRESHOLD = 210
DIFF = 45
HEIGHT = 733

source_dir = "../ferrari-nla/wp-content/uploads/images/f360_parts"
backup_dir = os.path.join(source_dir, "backup")
os.makedirs(backup_dir, exist_ok=True)

# 1. Load reference density image as uint16 array
ref_img = Image.open("output_average.webp").convert("L")
ref_matrix = np.array(ref_img, dtype=np.int16)[:HEIGHT, :]

image_paths = sorted(glob.glob(os.path.join(source_dir, "*.webp")))

for path in image_paths:
    filename = os.path.basename(path)
    backup_path = os.path.join(backup_dir, filename)

    # Backup original before modifying
    shutil.copy2(path, backup_path)

    # 2. Load target image
    img = Image.open(path).convert("L")
    img_matrix = np.array(img, dtype=np.int16)[:HEIGHT, :]

    # 3. Vectorized logic application:
    # Default output array starts identical to the input image
    out_matrix = img_matrix.copy()

    # Condition 1: Pixel value is greater than or equal to THRESHOLD (>= 203)
    thresh_mask = img_matrix >= THRESHOLD

    # Condition 2: Absolute difference from reference is less than DIFF (< 10)
    diff_mask = np.abs(img_matrix - ref_matrix) < DIFF

    # Combine conditions: apply 255 where BOTH masks are True
    out_matrix[thresh_mask & diff_mask] = 255

    # 4. Save resultant 8-bit image back to disk
    result_img = Image.fromarray(out_matrix.astype(np.uint8))
    result_img.save(path)
