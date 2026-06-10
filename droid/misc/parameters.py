import os
from cv2 import aruco

# Robot Params #
nuc_ip = "192.168.1.7"
robot_ip = "192.168.1.11"
laptop_ip = "192.168.1.6"
sudo_password = ""
robot_type = "fr3"  # 'panda' or 'fr3'
robot_serial_number = ""

# Camera ID's #
hand_camera_id = "10163006"  # ZED-M on gripper
varied_camera_1_id = "38845842"
varied_camera_2_id = "38924636"

# Charuco Board Params #
CHARUCOBOARD_ROWCOUNT = 9
CHARUCOBOARD_COLCOUNT = 14
CHARUCOBOARD_CHECKER_SIZE = 0.020
CHARUCOBOARD_MARKER_SIZE = 0.016
ARUCO_DICT = aruco.Dictionary_get(aruco.DICT_5X5_100)

# Ubuntu Pro Token (RT PATCH) #
ubuntu_pro_token = ""

# Code Version [DONT CHANGE] #
droid_version = "1.3"

