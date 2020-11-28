import os
import pandas as pd
import numpy as np
from pykml.factory import KML_ElementMaker as KML
from lxml import etree
from geopy import distance

# Change the below variable to be which ever file you want to parse out.
# If left blank it will run all files in the FILES_TO_WORK directory
GPS_DATA_FILENAME = "FILES_TO_WORK/2019_03_03__1523_18.txt"


def main(file):
    """
    Runs the main program.
    :param file: the file
    :return: N/A
    """
    GPGGA_data, GPRMC_data, coords_data = set_gps_data(file)
    pd.set_option('display.max_columns', 20)
    GPGGA_df = pd.DataFrame(GPGGA_data)
    GPRMC_df = pd.DataFrame(GPRMC_data)
    coords_df = pd.DataFrame(coords_data)
    coords_df.dropna(inplace=True)
    new_column = GPRMC_df["track made good in degrees"].values
    new_column = np.array(new_column).astype(float)
    GPRMC_df["speed over ground in knots"] = GPRMC_df["speed over ground in knots"].astype(float)
    new_column[1:] = new_column[1:] - new_column[:-1]
    for i, d in enumerate(new_column):
        # loops through the angle column to eliminate very large directional changes
        # because signs cause huge direction changes when crossing an axis
        # (i.e from 1 to 359 is only 2 degrees in practice)
        diff = d % 360
        result = diff if diff < 180 else 360 - diff
        sign = 1 if (0 <= d <= 180) or (-180 >= d >= -360) else -1
        new_column[i] = result * sign
    new_column[0] = new_column[1]
    new_column[-1] = new_column[-2]
    GPRMC_df["angle difference"] = new_column
    left_turns = GPRMC_df[np.logical_and(GPRMC_df["angle difference"] < -5, GPRMC_df["speed over ground in knots"] > 3)]
    left_turns = left_turns[np.logical_and(left_turns["angle difference"] > -300, left_turns["speed over ground in knots"] > 3)]
    right_turns = GPRMC_df[np.logical_and(GPRMC_df["angle difference"] > 5, GPRMC_df["speed over ground in knots"] > 3)]
    right_turns = right_turns[np.logical_and(right_turns["angle difference"] < 300, right_turns["speed over ground in knots"] > 3)]
    coords_df.drop_duplicates(subset=["longitude", "latitude"], keep="first", inplace=True)
    Right_turn = []
    for row in right_turns.iterrows():
        Right_turn.append([row[1][3], row[1][2]])
    Left_turn = []
    for row in left_turns.iterrows():
        Left_turn.append([row[1][3], row[1][2]])
    stopping_points = []

    for row in GPRMC_df.iterrows():
        #print(row)
        if float(row[1][4]) < 0.1:  # classifier 1: basically must not be moving
            stopping_points.append([row[1][3], row[1][2]])
    points_to_delete = set()
    for i in range(len(stopping_points)):
        #print(stopping_points[i])
        for j in range(i + 1, len(stopping_points)):
            dist = distance.distance(stopping_points[i], stopping_points[j]).m
            if dist < 10:  # multiple consecutive points where the car is not moving are removed
                points_to_delete.add(j)

    new_stopping_list = [stopping_points[i] for i in range(len(stopping_points)) if i not in points_to_delete]
    coordinates = ""
    for row in GPRMC_df.iterrows():
        if pd.notnull(row[1][0]):
            coordinates += f"{row[1][3]},{row[1][2]},0.0\n"

    kml_stops(new_stopping_list, file)
    kml_left_turns(Left_turn, file)
    kml_right_turns(Right_turn, file)


def kml_stops(kml_coordinates, filename):
    """
    TODO change colors to: magenta (stops) yellow (left) cyan (right)
    TODO combine stops and turns into one "hazards.kml" file
    """
    docs = KML.Document()
    for coord in kml_coordinates:
        doc = KML.Placemark(
            KML.description("testpath"),
            KML.Style(
                KML.IconStyle(
                    KML.color("ff0000ff"),
                    KML.Icon(
                        KML.href("http://maps.google.com/mapfiles/kml/paddle/1.png")
                    )
                )
            ),
            KML.Point(
                KML.coordinates(
                    str(coord[0]) + "," + str(coord[1]) + ",0.0"
                )
            )
        )
        docs.append(doc)

    head = KML.kml(docs)
    outputFilename = "Output_CostMap/" + filename[:-4].split("/")[-1] + "_stops.kml"
    outfile = open(outputFilename, "w")
    outfile.write(etree.tostring(head, pretty_print=True).decode())
    outfile.close()


def kml_left_turns(kml_coordinates, filename):
    docs = KML.Document()
    for coord in kml_coordinates:
        doc = KML.Placemark(
            KML.description("testpath"),
            KML.Style(
                KML.IconStyle(
                    KML.color("ff0000ff"),
                    KML.Icon(
                        KML.href("http://maps.google.com/mapfiles/kml/paddle/1.png")
                    )
                )
            ),
            KML.Point(
                KML.coordinates(
                    str(coord[0]) + "," + str(coord[1]) + ",0.0"
                )
            )
        )
        docs.append(doc)
    head = KML.kml(docs)
    outputFilename = "Output_CostMap/" + filename[:-4].split("/")[-1] + "_left.kml"
    outfile = open(outputFilename, "w")
    outfile.write(etree.tostring(head, pretty_print=True).decode())
    outfile.close()


def kml_right_turns(kml_coordinates, filename):
    docs = KML.Document()
    for coord in kml_coordinates:
        doc = KML.Placemark(
            KML.description("testpath"),
            KML.Style(
                KML.IconStyle(
                    KML.color("ff00ffff"),
                    KML.Icon(
                        KML.href("http://maps.google.com/mapfiles/kml/paddle/1.png")
                    )
                )
            ),
            KML.Point(
                KML.coordinates(
                    str(coord[0]) + "," + str(coord[1]) + ",0.0"
                )
            )
        )
        docs.append(doc)
    head = KML.kml(docs)
    outputFilename = "Output_CostMap/" + filename[:-4].split("/")[-1] + "_right.kml"
    outfile = open(outputFilename, "w")
    outfile.write(etree.tostring(head, pretty_print=True).decode())
    outfile.close()


def set_gps_data(data):
    GPGGA = {"UTC position": [], "latitude": [], "longitude": [],
             "GPS Fix": [], "# of Satellites": [], "Horizontal dilution of precision": [],
             "antenna altitude": [], "geoidal separation": [], "age of GPS data": [],
             "Differential reference station ID": []}
    GPRMC = {"UTC position": [], "validity": [], "latitude": [], "longitude": [],
             "speed over ground in knots": [], "track made good in degrees": [],
             "UT date": [], "variation": [], "checksum": []}
    coords = {"longitude": [], "latitude": [], "altitude": [], "speed": [], "sattelites": [], "angle": [], "fix": []}
    with open(data) as gps_file:
        for line in gps_file:
            line_tokens = line.split(",")
            if line_tokens[0] == "$GPGGA":
                GPGGA["UTC position"].append(float(line_tokens[1]))
                GPGGA["latitude"].append([line_tokens[2], line_tokens[3]])
                GPGGA["longitude"].append([line_tokens[4], line_tokens[5]])
                GPGGA["GPS Fix"].append(line_tokens[6])
                GPGGA["# of Satellites"].append(line_tokens[7])
                GPGGA["Horizontal dilution of precision"].append(line_tokens[8])
                GPGGA["antenna altitude"].append([line_tokens[9], line_tokens[10]])
                try:
                    GPGGA["geoidal separation"].append([line_tokens[11], line_tokens[12]])
                except IndexError:
                    GPGGA["geoidal separation"].append(None)
                try:
                    GPGGA["age of GPS data"].append(line_tokens[13])
                except IndexError:
                    GPGGA["age of GPS data"].append(None)
                try:
                    GPGGA["Differential reference station ID"].append(line_tokens[14].strip('\n'))
                except IndexError:
                    GPGGA["Differential reference station ID"].append(None)
            elif line_tokens[0] == "$GPRMC":
                GPRMC["UTC position"].append(float(line_tokens[1]))
                GPRMC["validity"].append(line_tokens[2])
                try:
                    if line_tokens[4] == "S":
                        GPRMC["latitude"].append(convert_coordinate(-1 * float(line_tokens[3])))
                    else:
                        GPRMC["latitude"].append(convert_coordinate(float(line_tokens[3])))
                    if line_tokens[6] == "W":
                        GPRMC["longitude"].append(convert_coordinate(-1 * float(line_tokens[5])))
                    else:
                        GPRMC["longitude"].append(convert_coordinate(float(line_tokens[5])))
                    GPRMC["speed over ground in knots"].append(float(line_tokens[7]))
                except ValueError:
                    GPRMC["latitude"].append(None)
                    GPRMC["longitude"].append(None)
                    GPRMC["speed over ground in knots"].append(None)
                GPRMC["track made good in degrees"].append(line_tokens[8])
                GPRMC["UT date"].append(line_tokens[9])
                try:
                    GPRMC["variation"].append([line_tokens[10], line_tokens[11]])
                except IndexError:
                    GPRMC["variation"].append(None)
                try:
                    GPRMC["checksum"].append(line_tokens[12].strip('\n'))
                except IndexError:
                    GPRMC["checksum"].append(None)
            elif "lng" in line_tokens[0]:
                lng = line_tokens[0].split("=")
                coords["longitude"].append(lng[1])
                lat = line_tokens[1].split("=")
                coords["latitude"].append(lat[1])
                alt = line_tokens[2].split("=")
                coords["altitude"].append(alt[1])
                spd = line_tokens[3].split("=")
                coords["speed"].append(spd[1])
                sat = line_tokens[4].split("=")
                coords["sattelites"].append(sat[1])
                ang = line_tokens[5].split("=")
                coords["angle"].append(ang[1])
                fix = line_tokens[6].split("=")
                coords["fix"].append(fix[1])

    return GPGGA, GPRMC, coords


def convert_time(utc_time):
    hours = int(utc_time / 10000)
    minutes_seconds = utc_time % 10000
    minutes = int(minutes_seconds / 100)
    seconds = minutes_seconds % 100
    return hours * 3600 + minutes * 60 + seconds


def convert_coordinate(coordinate):
    sign = 1
    if int(coordinate) < 0:
        sign = -1
    degrees = int(abs(coordinate) / 100)
    minutes = float(abs(coordinate)) % 100
    return sign * (degrees + (minutes / 60))


if __name__ == '__main__':
    if GPS_DATA_FILENAME == "":
        for fileName in os.listdir("FILES_TO_WORK"):
            main(fileName)
    else:
        main(GPS_DATA_FILENAME)
