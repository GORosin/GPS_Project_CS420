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
    GPGGA_data, GPRMC_data = get_gps_data(file)
    GPSData = format_gps_data(GPRMC_data, GPGGA_data)

    # gets rid of coordinates at exactly the same place
    coordinates = ""
    for row in GPSData.iterrows():
        if pd.notnull(row[1][0]):
            coordinates += f"{row[1][2]},{row[1][1]},0.0\n"  # creates a string of comma-separated coordinates
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


def get_gps_data(data):
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
    with open(data) as gps_file:
        for line in gps_file:
            line_tokens = line.split(",")  # splits data by commas

            if line_tokens[0] == "$GPGGA":  # if the first item in a line is GPGGA add it to that dictionary
                if line_tokens[2] == "" or line_tokens[4] == "":
                    continue
                GPGGA["UTC position"].append(float(line_tokens[1]))
                if line_tokens[3] == "S":
                    GPGGA["latitude"].append(float(line_tokens[2]) * -1 / 100)
                else:
                    GPGGA["latitude"].append(float(line_tokens[2]) / 100)
                if line_tokens[5] == "W":
                    GPGGA["longitude"].append(float(line_tokens[4]) * -1 / 100)
                else:
                    GPGGA["longitude"].append(float(line_tokens[4]) / 100)
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
                GPRMC["UTC position"].append(float(line_tokens[1]))
                GPRMC["validity"].append(line_tokens[2])
                if line_tokens[4] == "S":
                    GPRMC["latitude"].append(float(line_tokens[3]) * -1 / 100)
                else:
                    GPRMC["latitude"].append(float(line_tokens[3]) / 100)
                if line_tokens[6] == "W":
                    GPRMC["longitude"].append(float(line_tokens[5]) * -1 / 100)
                else:
                    GPRMC["longitude"].append(float(line_tokens[5]) / 100)
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
                GPSData["latitude"].append(GPRMC_data["latitude"][counterRMC])
            else:
                GPSData["latitude"].append(GPGGA_data["latitude"][counterGGA])
            if GPRMC_data["longitude"][counterRMC] != "":
                GPSData["longitude"].append(GPRMC_data["longitude"][counterRMC])
            else:
                GPSData["longitude"].append(GPGGA_data["longitude"][counterGGA])
            GPSData["speed"].append(GPRMC_data["speed over ground in knots"][counterRMC] * 1.1508)
            GPSData["angle"].append(GPRMC_data["track made good in degrees"][counterRMC])
            GPSData["satellites"].append(GPGGA_data["# of Satellites"][counterGGA])
            counterRMC += 1
            counterGGA += 1
        elif timeRMC < timeGGA:
            GPSData["time"].append(timeRMC)
            GPSData["latitude"].append(GPRMC_data["latitude"][counterRMC])
            GPSData["longitude"].append(GPRMC_data["longitude"][counterRMC])
            GPSData["speed"].append(GPRMC_data["speed over ground in knots"][counterRMC] * 1.1508)
            GPSData["angle"].append(GPRMC_data["track made good in degrees"][counterRMC])
            GPSData["satellites"].append(GPGGA_data["# of Satellites"][counterGGA])
            counterRMC += 1
        elif timeGGA < timeRMC:
            GPSData["time"].append(timeGGA)
            GPSData["latitude"].append(GPGGA_data["latitude"][counterGGA])
            GPSData["longitude"].append(GPGGA_data["longitude"][counterGGA])
            GPSData["speed"].append(GPRMC_data["speed over ground in knots"][counterRMC] * 1.1508)
            GPSData["angle"].append(GPRMC_data["track made good in degrees"][counterRMC])
            GPSData["satellites"].append(GPGGA_data["# of Satellites"][counterGGA])
            counterGGA += 1
        if counterRMC >= len(GPRMC_data["UTC position"]) or counterGGA >= len(GPGGA_data["UTC position"]):
            timeRMC = 0
            timeGGA = 0
        else:
            timeRMC = GPRMC_data["UTC position"][counterRMC]
            timeGGA = GPGGA_data["UTC position"][counterGGA]

    # convert data into a pandas dataframe
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
