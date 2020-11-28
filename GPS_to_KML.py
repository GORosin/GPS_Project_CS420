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
    # pandas data frames created for GPS data
    GPGGA_df = pd.DataFrame(GPGGA_data)
    GPRMC_df = pd.DataFrame(GPRMC_data)
    coords_df = pd.DataFrame(coords_data)
    GPRMC_df.dropna(inplace=True)  # get rid of NaNs
    coords_df.dropna(inplace=True)
    GPRMC_df.drop_duplicates(subset=["UTC position"], keep="first", inplace=True)
    # get rid of coordinates recorded at the same time (if any)
    gps_speed_in_knots = []  # list of speeds calculated manually (used to compare to listed speeds)
    GPRMC_df.reset_index(drop=True, inplace=True)
    for idx in range(len(GPRMC_df) - 1):
        longi1 = GPRMC_df["longitude"][idx]
        longi2 = GPRMC_df["longitude"][idx + 1]
        lat1 = GPRMC_df["latitude"][idx]
        lat2 = GPRMC_df["latitude"][idx + 1]
        time1 = convert_time(GPRMC_df["UTC position"][idx])
        time2 = convert_time(GPRMC_df["UTC position"][idx + 1])
        try:
            distanceDifference = distance.distance((longi1 / 100, lat1 / 100), (longi2 / 100, lat2 / 100)).m
            timeDifference = time2 - time1
            speed = distanceDifference / timeDifference * 2  # calculates speed as distance/time (m/s)
            gps_speed_in_knots.append(round(speed, 2))

        except (TypeError, KeyError) as e:
            gps_speed_in_knots.append(None)

    coords_df["speed"] = coords_df["speed"].astype(float)  # converts speed column to float
    gps_speed_in_knots.append(gps_speed_in_knots[-1])
    meanList = []
    midList = []
    for i in range(50):
        bin_data = GPRMC_df[np.logical_and(GPRMC_df["speed over ground in knots"] > i / 10,
                                           GPRMC_df["speed over ground in knots"] < (i + 1) / 10)]
        midpoint = (2 * i + 1) / 20
        midList.append(midpoint)
    GPRMC_df["calculated speed"] = gps_speed_in_knots
    GPRMC_df.dropna(inplace=True)  # drops NaNs from calculated speed
    GPRMC_df.drop_duplicates(subset=["longitude", "latitude"], keep="first", inplace=True)
    coords_df.drop_duplicates(subset=["longitude", "latitude"], keep="first", inplace=True)
    # gets rid of coordinates at exactly the same place
    coordinates = ""
    for row in GPRMC_df.iterrows():
        if pd.notnull(row[1][0]):
            coordinates += f"{row[1][3]},{row[1][2]},0.0\n"  # creates a string of comma-separated coordinates
    to_kml(coordinates, file)


def to_kml(kml_coordinates, filename):
    """
    Creates a KML file using coordinates listed in a txt file.
    :param kml_coordinates: String of comma-separated coordinates (longitude, latitude, speed)
    :param filename: name of the txt file being converted
    """
    doc = KML.kml(
        KML.Document(
            KML.Style(
                KML.LineStyle(
                    KML.color("Af00ffff")
                )
            ),
            KML.Placemark(
                KML.name("placeholder"),
                KML.description("testpath"),
                KML.LineString(
                    KML.coordinates(
                        kml_coordinates
                    )
                )
            )
        )
    )
    outputFilename = "Output_KML/" + filename[:-3].split("/")[-1] + "kml"
    outfile = open(outputFilename, "w")
    outfile.write(etree.tostring(doc, pretty_print=True).decode())
    outfile.close()


def set_gps_data(data):
    """
    Creates three dictionaries of GPS data using GPGGA, GPRMC, and listed coordinates.
    See: http://aprs.gids.nl/nmea/
    :param data: Name of a txt file where GPS data is retrieved.
    :return: GPGGA, GPRMC, Coords dictionaries
    """
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
            line_tokens = line.split(",")  # splits data by commas
            if line_tokens[0] == "$GPGGA":  # if the first item in a line is GPGGA add it to that dictionary
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
                except IndexError:  # if this column is empty make it none for length consistency
                    GPRMC["variation"].append(None)
                try:
                    GPRMC["checksum"].append(line_tokens[12].strip('\n'))
                except IndexError:
                    GPRMC["checksum"].append(None)
            elif "lng" in line_tokens[0]:  # coordinates are split by =
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
