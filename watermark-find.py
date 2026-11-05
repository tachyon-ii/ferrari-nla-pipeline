#!/usr/bin/env python3

import glob
import numpy as np
from PIL import Image

# 1. Collect image file paths
image_paths = sorted(glob.glob("../ferrari-nla/wp-content/uploads/images/f360_parts/*.webp"))
total_images = len(image_paths)

# 2. Load the first image to establish dimensions and initialize a float accumulator
first_img = Image.open(image_paths[0]).convert("L")
accumulator = np.array(first_img, dtype=np.float64)

# 3. Sum pixel values across the remaining images
for path in image_paths[1:]:
    img = Image.open(path).convert("L")
    accumulator += np.array(img, dtype=np.float64)

# 4. Divide by total count (106)
density_matrix = accumulator / total_images

# 5. Convert back to 8-bit uint8 and write the resultant image
result_img = Image.fromarray(np.round(density_matrix).astype(np.uint8))
result_img.save("output_average.webp")
