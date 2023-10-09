from PIL import Image
import pytesseract as pt
import numpy as np
from enum import Enum
import validators
import requests
import cv2

pt.pytesseract.tesseract_cmd = r'C:/Program Files/Tesseract-OCR/tesseract.exe'

class Output(Enum):
    RAW = 1
    LIST = 2

def extract_from_image(image, x1 = 0, x2 = 0, y1 = 0, y2 = 0, crop = False, output = Output.RAW):
    img = image
    if validators.url(image):
        im = Image.open(requests.get(image, stream=True).raw)
        img = np.array(im)
        rez = image_resize(img, 1920, 1080)
        if crop:
            (h, w) = rez.shape[:2]
            x2 = h if x2 == 0 else h + x2 if x2 < 0 else x2

            img = rez[x1:x2, y1:y2]
    text = pt.image_to_string(img, nice=100)
    if output == Output.RAW:
        return text
    elif output == Output.LIST:
        result = text.split("\n")
        return list(filter(None, result))
    return None

def image_resize(image, width = None, height = None, inter = cv2.INTER_AREA):
    # initialize the dimensions of the image to be resized and
    # grab the image size
    dim = None
    (h, w) = image.shape[:2]

    # if both the width and height are None, then return the
    # original image
    if width is None and height is None:
        return image

    # check to see if the width is None
    if width is None:
        # calculate the ratio of the height and construct the
        # dimensions
        r = height / float(h)
        dim = (int(w * r), height)

    # otherwise, the height is None
    else:
        # calculate the ratio of the width and construct the
        # dimensions
        r = width / float(w)
        dim = (width, int(h * r))

    # resize the image
    resized = cv2.resize(image, dim, interpolation = inter)

    # return the resized image
    return resized