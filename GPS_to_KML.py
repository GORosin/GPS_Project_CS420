import sys
import os
import webbrowser
import math
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pykml.factory import KML_ElementMaker as KML
from lxml import etree
from geopy import distance
import datetime


def to_kml(kml_coordinates, filename):
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
    outfile = open(str(filename[:-3]) + "kml", "w")
    outfile.write(etree.tostring(doc, pretty_print=True).decode())
    outfile.close()
    # os.startfile(outfile.name)


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
                        GPRMC["latitude"].append(-1 * float(line_tokens[3]))
                    else:
                        GPRMC["latitude"].append(float(line_tokens[3]))
                    if line_tokens[6] == "W":
                        GPRMC["longitude"].append(-1 * float(line_tokens[5]))
                    else:
                        GPRMC["longitude"].append(float(line_tokens[5]))
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


def calc_mid(interval):
    return int(interval.mid)


if __name__ == '__main__':
    files = [f for f in os.listdir('.') if os.path.isfile(f)]
    for file in files:
        if file[-3:] != "txt":
            continue
        else:
            gps_data = file
            print(file)
            GPGGA_data, GPRMC_data, coords_data = set_gps_data(gps_data)
            pd.set_option('display.max_columns', 20)
            GPGGA_df = pd.DataFrame(GPGGA_data)
            GPRMC_df = pd.DataFrame(GPRMC_data)
            coords_df = pd.DataFrame(coords_data)
            GPRMC_df.dropna(inplace=True)
            coords_df.dropna(inplace=True)
            GPRMC_df.drop_duplicates(subset=["UTC position"], keep="first", inplace=True)
            gps_speed_in_knots = []
            directionchange = []
            GPRMC_df.reset_index(drop=True, inplace=True)
            for idx in range(len(GPRMC_df) - 1):
                longi1 = GPRMC_df["longitude"][idx]
                longi2 = GPRMC_df["longitude"][idx + 1]
                lat1 = GPRMC_df["latitude"][idx]
                lat2 = GPRMC_df["latitude"][idx + 1]
                time1 = convert_time(GPRMC_df["UTC position"][idx])
                time2 = convert_time(GPRMC_df["UTC position"][idx + 1])
                direction1 = GPRMC_df["track made good in degrees"][idx]
                direction2 = GPRMC_df["track made good in degrees"][idx + 1]
                try:
                    distancedifference = distance.distance((longi1 / 100, lat1 / 100), (longi2 / 100, lat2 / 100)).m
                    timedifference = time2 - time1
                    directiondifference = abs(float(direction2) - float(direction1))
                    speed = distancedifference / timedifference * 2
                    gps_speed_in_knots.append(round(speed, 2))

                except (TypeError, KeyError) as e:
                    gps_speed_in_knots.append(None)

            coords_df["speed"] = coords_df["speed"].astype(float)
            gps_speed_in_knots.append(gps_speed_in_knots[-1])
            meanlist = []
            midlist = []
            for i in range(50):
                bin_data = GPRMC_df[np.logical_and(GPRMC_df["speed over ground in knots"] > i / 10,
                                                   GPRMC_df["speed over ground in knots"] < (i + 1) / 10)]
                midpoint = (2 * i + 1) / 20
                midlist.append(midpoint)
            GPRMC_df["calculated speed"] = gps_speed_in_knots
            GPRMC_df.dropna(inplace=True)
            GPRMC_df.drop_duplicates(subset=["longitude", "latitude"], keep="first", inplace=True)
            coords_df.drop_duplicates(subset=["longitude", "latitude"], keep="first", inplace=True)

            coordinates = ""
            for row in coords_df.iterrows():
                if pd.notnull(row[1][0]):
                    coordinates += f"{row[1][0]},{row[1][1]},0.0\n"

            to_kml(coordinates, file)
