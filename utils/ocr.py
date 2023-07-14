# import re
# import cv2
# import numpy as np
# import pytesseract
# from pytesseract import Output

# # pytesseract.pytesseract.tesseract_cmd = r'C:\\Users\\USER\\AppData\\Local\\Tesseract-OCR\\tesseract.exe'

# img = cv2.imread('invoice-sample.jpg')
# d = pytesseract.image_to_data(img, output_type=Output.DICT)
# keys = list(d.keys())

# date_pattern = '^(0[1-9]|[12][0-9]|3[01])/(0[1-9]|1[012])/(19|20)\d\d$'

# n_boxes = len(d['text'])
# for i in range(n_boxes):
#     if int(d['conf'][i]) > 60:
#     	if re.match(date_pattern, d['text'][i]):
# 	        (x, y, w, h) = (d['left'][i], d['top'][i], d['width'][i], d['height'][i])
# img = cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)

# cv2.imshow('img', img)
# cv2.waitKey(0)

# # get grayscale image
# def get_grayscale(image):
#     return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

# # noise removal
# def remove_noise(image):
#     return cv2.medianBlur(image,5)
 
# #thresholding
# def thresholding(image):
#     return cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

# #dilation
# def dilate(image):
#     kernel = np.ones((5,5),np.uint8)
#     return cv2.dilate(image, kernel, iterations = 1)
    
# #erosion
# def erode(image):
#     kernel = np.ones((5,5),np.uint8)
#     return cv2.erode(image, kernel, iterations = 1)

# #opening - erosion followed by dilation
# def opening(image):
#     kernel = np.ones((5,5),np.uint8)
#     return cv2.morphologyEx(image, cv2.MORPH_OPEN, kernel)

# #canny edge detection
# def canny(image):
#     return cv2.Canny(image, 100, 200)

# #skew correction
# def deskew(image):
#     coords = np.column_stack(np.where(image > 0))
#     angle = cv2.minAreaRect(coords)[-1]
#     if angle < -45:
#         angle = -(90 + angle)
#     else:
#         angle = -angle
#     (h, w) = image.shape[:2]
#     center = (w // 2, h // 2)
#     M = cv2.getRotationMatrix2D(center, angle, 1.0)
#     rotated = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
#     return rotated

# #template matching
# def match_template(image, template):
#     return cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED) 

from PIL import Image
import pytesseract as pt
import numpy as np
from enum import Enum
import validators
import requests
import cv2
import re

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