import os
import pandas as pd
import numpy as np
from pykml.factory import KML_ElementMaker as KML
from lxml import etree
from geopy import distance

# Change the below variable to be which ever file you want to parse out.
# If left blank it will run all files in the FILES_TO_WORK directory
GPS_DATA_FILENAME = ""


def main(file):
    """
    Runs the main program.
    :param file: the file
    :return: stops, left_turn, right_turn
    """
    GPGGA_data, GPRMC_data = set_gps_data(file)
    GPSData = format_gps_data(GPRMC_data, GPGGA_data)

    pd.set_option('display.max_columns', 20)
    change_in_direction = GPSData["angle"].values
    change_in_direction = np.array(change_in_direction).astype(float)  # convert elements to float
    change_in_direction[1:] = change_in_direction[1:] - change_in_direction[:-1]
    for idx, direction in enumerate(change_in_direction):
        # loops through the angle column to eliminate very large directional changes
        # because signs cause huge direction changes when crossing an axis
        # (i.e from 1 to 359 is only 2 degrees in practice)
        diff = direction % 360
        result = diff if diff < 180 else 360 - diff
        sign = 1 if (0 <= direction <= 180) or (-180 >= direction >= -360) else -1
        change_in_direction[idx] = result * sign
    change_in_direction[0] = change_in_direction[1]
    change_in_direction[-1] = change_in_direction[-2]
    GPSData["angle difference"] = change_in_direction
    left_turns = GPSData[np.logical_and(GPSData["angle difference"] < -5, GPSData["speed"] > 3)]
    left_turns = left_turns[np.logical_and(left_turns["angle difference"] > -8, left_turns["speed"] < 25)]
    right_turns = GPSData[np.logical_and(GPSData["angle difference"] > 5, GPSData["speed"] > 3)]
    right_turns = right_turns[np.logical_and(right_turns["angle difference"] < 8, right_turns["speed"] < 25)]
    right_turn_list = []
    points_to_delete = set()
    for row in right_turns.iterrows():  # there's probably a more efficient way to convert the column to a list
        right_turn_list.append([row[1][2], row[1][1]])
    for idx in range(len(right_turn_list)):
        for j in range(idx + 1, len(right_turn_list)):
            dist = distance.distance(right_turn_list[idx], right_turn_list[j]).m
            if dist < 8:  # multiple consecutive points where the car is not moving are removed
                points_to_delete.add(j)
    right_turn_list = [right_turn_list[i] for i in range(len(right_turn_list)) if i not in points_to_delete]

    points_to_delete = set()
    left_turn_list = []
    for row in left_turns.iterrows():
        left_turn_list.append([row[1][2], row[1][1]])
    for idx in range(len(left_turn_list)):
        for j in range(idx + 1, len(left_turn_list)):
            dist = distance.distance(left_turn_list[idx], left_turn_list[j]).m
            if dist < 8:  # multiple consecutive points where the car is not moving are removed
                points_to_delete.add(j)
    left_turn_list = [left_turn_list[i] for i in range(len(left_turn_list)) if i not in points_to_delete]

    GPSData["speedavg"] = GPSData["speed"].rolling(10, center=True).mean()
    stops = GPSData[np.logical_and(GPSData["speed"] > 9, GPSData["speed"] < 12)]
    stops = stops[np.logical_and(stops["speedavg"] > 9, stops["speedavg"] < 12)]
    stopping_points = []
    for row in stops.iterrows():
        stopping_points.append([row[1][2], row[1][1]])
    points_to_delete = set()
    for idx in range(len(stopping_points)):
        for j in range(idx + 1, len(stopping_points)):
            dist = distance.distance(stopping_points[idx], stopping_points[j]).m
            if dist < 15:  # multiple consecutive points where the car is not moving are removed
                points_to_delete.add(j)
    new_stopping_list = [stopping_points[i] for i in range(len(stopping_points)) if i not in points_to_delete]
    coordinates = ""
    for row in GPSData.iterrows():
        if pd.notnull(row[1][0]):
            coordinates += f"{row[1][2]},{row[1][1]},0.0\n"

    return new_stopping_list, left_turn_list, right_turn_list


def kml_stops(kml_coordinates, docs):
    """
    creates a purple placemark for every coordinate classified as a stop
    """
    for coord in kml_coordinates:
        doc = KML.Placemark(
            KML.description("Stop"),
            KML.Style(
                KML.IconStyle(
                    KML.color("ff780078"),
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


def kml_left_turns(kml_coordinates, docs):
    """
    creates a yellow placemark for every coordinate classified as a left turn
    """
    for coord in kml_coordinates:
        doc = KML.Placemark(
            KML.description("Left Turn"),
            KML.Style(
                KML.IconStyle(
                    KML.color("FF14F0FF"),
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


def kml_right_turns(kml_coordinates, docs):
    """
    creates a cyan placemark for every coordinate classified as a right turn
    """
    for coord in kml_coordinates:
        doc = KML.Placemark(
            KML.description("Right Turn"),
            KML.Style(
                KML.IconStyle(
                    KML.color("ffffff00"),
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


def set_gps_data(data):
    """
    Creates three dictionaries of GPS data using GPGGA, GPRMC, and listed coordinates.
    See: http://aprs.gids.nl/nmea/
    :param data: Name of a txt file where GPS data is retrieved.
    :return: GPGGA, GPRMC dictionaries
    """
    GPGGA = {"UTC position": [], "latitude": [], "longitude": [],
             "GPS Fix": [], "# of Satellites": [], "Horizontal dilution of precision": [],
             "antenna altitude": [], "geoidal separation": [], "age of GPS data": [],
             "Differential reference station ID": []}
    GPRMC = {"UTC position": [], "validity": [], "latitude": [], "longitude": [],
             "speed over ground in knots": [], "track made good in degrees": [],
             "UT date": [], "variation": [], "checksum": []}
    with open(data) as gps_file:
        for line in gps_file:
            line_tokens = line.split(",")  # splits data by commas

            if line_tokens[0] == "$GPGGA":  # if the first item in a line is GPGGA add it to that dictionary
                if line_tokens[2] == "" or line_tokens[4] == "":
                    continue
                GPGGA["UTC position"].append(float(line_tokens[1]))
                if line_tokens[3] == "S":
                    GPGGA["latitude"].append(float(line_tokens[2]) * -1)
                else:
                    GPGGA["latitude"].append(float(line_tokens[2]))
                if line_tokens[5] == "W":
                    GPGGA["longitude"].append(float(line_tokens[4]) * -1)
                else:
                    GPGGA["longitude"].append(float(line_tokens[4]))
                GPGGA["GPS Fix"].append(int(line_tokens[6]))
                GPGGA["# of Satellites"].append(int(line_tokens[7]))
                GPGGA["Horizontal dilution of precision"].append(float(line_tokens[8]))
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
                if line_tokens[3] == "" or line_tokens[5] == "":
                    continue
                try:
                    float(line_tokens[5])
                except ValueError:
                    continue
                GPRMC["UTC position"].append(float(line_tokens[1]))
                GPRMC["validity"].append(line_tokens[2])
                if line_tokens[4] == "S":
                    GPRMC["latitude"].append(float(line_tokens[3]) * -1)
                else:
                    GPRMC["latitude"].append(float(line_tokens[3]))
                if line_tokens[6] == "W":
                    GPRMC["longitude"].append(float(line_tokens[5]) * -1)
                else:
                    GPRMC["longitude"].append(float(line_tokens[5]))
                GPRMC["speed over ground in knots"].append(float(line_tokens[7]))
                GPRMC["track made good in degrees"].append(float(line_tokens[8]))
                GPRMC["UT date"].append(line_tokens[9])
                try:
                    GPRMC["variation"].append([line_tokens[10], line_tokens[11]])
                except IndexError:  # if this column is empty make it none for length consistency
                    GPRMC["variation"].append(None)
                try:
                    GPRMC["checksum"].append(line_tokens[12].strip('\n'))
                except IndexError:
                    GPRMC["checksum"].append(None)
    return GPGGA, GPRMC


def format_gps_data(GPRMC_data, GPGGA_data):
    """

    :param GPRMC_data: Data in the GPRMC format.
    :param GPGGA_data: Data in the GPGGA format.
    :return: a dictionary with the following:
        time: The UTC time the position was recorded.
        Latitude: The latitude of the position.
        Longitude: The longitude of the position.
        Speed: The average speed between the previous position and the current one in MPH.
        Angle: The angle between the previous position and the current one, 0 is due north.
        Fix Quality: The quality of the gps positioning.
        Satellites: The number of satellites used in getting the position
    """

    GPSData = {"time": [], "latitude": [], "longitude": [], "speed": [], "angle": [], "satellites": []}

    counterRMC = 0
    counterGGA = 0
    timeRMC = GPRMC_data["UTC position"][counterRMC]
    timeGGA = GPGGA_data["UTC position"][counterGGA]

    while timeRMC != 0 and timeGGA != 0:
        if timeRMC == timeGGA:
            GPSData["time"].append(timeRMC)
            if GPRMC_data["latitude"][counterRMC] != "":
                GPSData["latitude"].append(convert_coordinate(GPRMC_data["latitude"][counterRMC]))
            else:
                GPSData["latitude"].append(convert_coordinate(GPGGA_data["latitude"][counterGGA]))
            if GPRMC_data["longitude"][counterRMC] != "":
                GPSData["longitude"].append(convert_coordinate(GPRMC_data["longitude"][counterRMC]))
            else:
                GPSData["longitude"].append(convert_coordinate(GPGGA_data["longitude"][counterGGA]))
            GPSData["speed"].append(GPRMC_data["speed over ground in knots"][counterRMC] * 1.1508)
            GPSData["angle"].append(GPRMC_data["track made good in degrees"][counterRMC])
            GPSData["satellites"].append(GPGGA_data["# of Satellites"][counterGGA])
            counterRMC += 1
            counterGGA += 1
        elif timeRMC < timeGGA:
            GPSData["time"].append(timeRMC)
            GPSData["latitude"].append(convert_coordinate(GPRMC_data["latitude"][counterRMC]))
            GPSData["longitude"].append(convert_coordinate(GPRMC_data["longitude"][counterRMC]))
            GPSData["speed"].append(GPRMC_data["speed over ground in knots"][counterRMC] * 1.1508)
            GPSData["angle"].append(GPRMC_data["track made good in degrees"][counterRMC])
            GPSData["satellites"].append(GPGGA_data["# of Satellites"][counterGGA])
            counterRMC += 1
        elif timeGGA < timeRMC:
            counterGGA += 1
        if counterRMC >= len(GPRMC_data["UTC position"]) or counterGGA >= len(GPGGA_data["UTC position"]):
            timeRMC = 0
            timeGGA = 0
        else:
            timeRMC = GPRMC_data["UTC position"][counterRMC]
            timeGGA = GPGGA_data["UTC position"][counterGGA]

    # convert data into a pandas data frame
    pd.set_option('display.max_columns', 20)
    GPSData_df = pd.DataFrame(GPSData)
    GPSData_df.dropna(inplace=True)  # get rid of NaNs
    GPSData_df.drop_duplicates(subset=["time"], keep="first", inplace=True)

    return GPSData_df


def convert_time(utc_time):
    """
    converts a UTC position from hours, minutes, seconds into just seconds.
    easier to do math with time in one unit.
    returns time in seconds.
    """
    hours = int(utc_time / 10000)
    minutes_seconds = utc_time % 10000
    minutes = int(minutes_seconds / 100)
    seconds = minutes_seconds % 100
    return hours * 3600 + minutes * 60 + seconds


def convert_coordinate(coordinate):
    """
    converts latitude or longitude from degrees + minutes to just degrees
    returns coordinate in degrees
    """
    sign = 1
    if int(coordinate) < 0:  # i.e if negative, conserve the sign so it doesn't mess up the calculation
        sign = -1
    degrees = int(abs(coordinate) / 100)
    minutes = float(abs(coordinate)) % 100
    return sign * (degrees + (minutes / 60))


def create_output_file(header, filename):
    """
    :param header: a KML.kml object enclosing documents
    :param filename: name of the file to write
    """
    if not os.path.exists('Output_CostMap/'):
        os.makedirs('Output_CostMap/')
    outputFilename = "Output_CostMap/" + filename[:-4].split("/")[-1] + "_Hazards.kml"
    outfile = open(outputFilename, "w")
    outfile.write(etree.tostring(header, pretty_print=True).decode())
    outfile.close()


if __name__ == '__main__':
    if GPS_DATA_FILENAME == "":
        directory = "FILES_TO_WORK/"
        costmap = []
        kml_docs = KML.Document()
        for fileName in os.listdir(directory):
            stops, lefts, rights = main(directory+fileName)
            kml_stops(stops, kml_docs)
            kml_left_turns(lefts, kml_docs)
            kml_right_turns(rights, kml_docs)
        head = KML.kml(kml_docs)
        create_output_file(head, directory+"Example.kml")
    else:
        main(GPS_DATA_FILENAME)

