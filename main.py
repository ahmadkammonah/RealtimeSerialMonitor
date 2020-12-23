#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Last Update on Thu Dec 23 2020

@author: Ahmad Kammonah
"""
############################### Imports #################################
#########################################################################

import time
import os, glob
import requests
import logging
import pandas as pd
from csv import writer
from datetime import datetime
from threading import Timer

# Packages used for Serial Port Communication
import serial.tools.list_ports  # Used to find all Serial Ports
import serial  # Pyserial

# Packages to Uplaod to Plolty's ChartStudio
import chart_studio.plotly as py
from plotly.subplots import make_subplots
import plotly.graph_objects as go

# Package to Uplaod to Google Spreadsheet and Google Drive
import gspread
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

########################### TO-DO List ##################################
################### Follow this List Carefully ##########################

sleepTime = 1                     # TODO: Set Time to sleep between each cycle
uploadTimer = 900                 # TODO: Set Interval between each time plotlyloader() and googleDriveUploader() are called in Seconds. Minimum 900.
maxEmptyLines = 10                # TODO: Set maximum empty serial reads before declaring the port not connected
portBaudrate = 115200             # TODO: Set Port Baudrate

googleDriveFolder = "Raw Data"    # TODO: Set the folder name in Google Drive that will contain all Raw Data and Log File.
googleSpreadsheet = "Clean Data"  # TODO: Set the SpreadhSheet name !!! RENAME EACH SHEET TO THE ID OF EACH GP (e.g.: Instead os 'Sheet1' use 'GP_20150100') !!!

username = 'YOUR_USERNAME'  # TODO: Your Plolty Username
api_key = 'YOUR_API'  # TODO: Your Plotly Api key - go to profile > settings > regenerate key

gpList = ["ID1", "ID2", "ID3"] #TODO: Add all GP IDs exactly as they're outputed from each GP
rawDataPath = r'./rawData'        # TODO: Path to save Raw Data
cleanDataPath = r'./cleanData'    # TODO: Path to save Clean Data

############################### Logging #################################
#########################################################################

# Gets or creates a logger
logger = logging.getLogger("logger")

# set log level
logger.setLevel(logging.DEBUG)

# define file handler and set formatter
logTimeFormat = '%m/%d/%Y %I:%M:%S %p'
file_handler = logging.FileHandler('logfile.log')
formatter = logging.Formatter('%(asctime)s : %(levelname)s : %(message)s', datefmt=logTimeFormat)
file_handler.setFormatter(formatter)

# add file handler to logger
logger.addHandler(logging.StreamHandler())
logger.addHandler(file_handler)

######################## Repeated Timer Class ###########################
########### Class that handles Repeated Functions in Background #########
#########################################################################

class RepeatedTimer(object):
    def __init__(self, interval, function, *args, **kwargs):
        self._timer = None
        self.interval = interval
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.is_running = False
        self.start()

    def _run(self):
        self.is_running = False
        self.start()
        self.function(*self.args, **self.kwargs)

    def start(self):
        if not self.is_running:
            self._timer = Timer(self.interval, self._run)
            self._timer.start()
            self.is_running = True

    def stop(self):
        self._timer.cancel()
        self.is_running = False


###################### Google Drive Uploader ############################
#########################################################################

##  This function Handles Authentication to Access and Upload on Google Drive every 'uploadTimer' seconds
def googleDriveUploader():
    try:
        gauth = GoogleAuth()

        # Try to load saved client credentials
        gauth.LoadCredentialsFile("savedCredentials.txt")

        if gauth.credentials is None:
            # Prevents having to re-authenticate if token expires
            gauth.GetFlow()
            gauth.flow.params.update({'access_type': 'offline'})
            gauth.flow.params.update({'approval_prompt': 'force'})

            # Authenticate if they're not there
            gauth.LocalWebserverAuth()
        elif gauth.access_token_expired:
            # Refresh them if expired
            gauth.Refresh()
        else:
            # Initialize the saved creds
            gauth.Authorize()

        # Save the current credentials to a file
        gauth.SaveCredentialsFile("savedCredentials.txt")
        drive = GoogleDrive(gauth)

        # Queries Google Drive to find a specific folder 'googleDriveFolder'
        folders = drive.ListFile(
            {
                'q': "title='" + googleDriveFolder + "' and 'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"}).GetList()

        # Gets the ID of the folder (Without ID, Pydrive can only upload to the root of the drive and not inside a specific folder)
        folderID = ''
        for folder in folders:
            if folder['title'] == googleDriveFolder:
                folderID = folder['id']

        # Deletes All Files in the Drive to avoid double uploads of the same file
        file_list = drive.ListFile({'q': "'" + folderID + "' in parents and trashed=False"}).GetList()
        for file1 in file_list:
            try:
                for file1 in file_list:
                    file1.Delete()
            except:
                pass

        # Finds the Path of all Raw Data Files and Uploads them in For Loop
        all_files = glob.glob(os.path.join(rawDataPath, "rawGP_*.asc"))
        for file in all_files:
            f = drive.CreateFile({'parents': [{'id': folderID}]})
            f.SetContentFile(file)
            f.Upload()

        # Finally, Uploads Latest Log File Available
        f = drive.CreateFile({'parents': [{'id': folderID}]})
        f.SetContentFile("logfile.log")
        f.Upload()

        logger.info("Raw Data uploaded to Google Drive")

    except Exception as error:
        logger.error("Google Drive Uplaoder Failed.")
        logger.error(error)

######################### Google Spreadsheet Uplaoder ###################
#########################################################################

## Accepts a 'row' of data and 'ID' of GP and uploads to specific
## WARNING: If couldn't upload a row, the Function will not retry and that row will only be accessed through the Raw Data.
def googleUploader(row, ID):
    # Signs in to google Service account and opens specified spreadhseet 'googleSpreadsheet'
    gc = gspread.service_account(filename='./secret_key.json')
    spreadsheet = gc.open(googleSpreadsheet)

    # Appends Row to Worksheet with name 'ID'
    try:
        spreadsheet.worksheet(ID).append_row(row)
        logger.info(f"Successful upload to Google Spreadsheet {ID}")
    except (requests.ConnectionError, requests.Timeout):
        logger.error("Internet Connection failure while connecting to Google Spreadsheet")
    except Exception as error:
        logger.error("Failed Uploading to Google Spreadsheet")
        logger.error(error)


######################### Plolty ChartStudio Uplaoder ###################
#########################################################################

## This function combines all cleanData.csv files and uploads them to Plolty Chart Studio every 'uploadTimer' seconds
def ploltyUploader():
    # Signs in to Plolty Account using specified username and Api Key
    py.sign_in(username, api_key)

    try:
        # Make a list of all CSV files to merge
        all_files = glob.glob(os.path.join("./cleanData/", "GP_*.csv"))

        # Combine all files in the list
        df = pd.concat(
            [pd.read_csv(f, names=["Datetime", "CO2", "Temp", "Pressure", "ID"], error_bad_lines=False) for f in all_files])
        df = df.sort_values(by='Datetime')

        #Seperates Date and Time For the purposes of Plotting
        df['Datetime'] = pd.to_datetime(df['Datetime'])
        df['date'] = df['Datetime'].dt.date
        df['time'] = df['Datetime'].dt.time

        # Deletes from top of datafram to make sure Dataframe does not exceed 500KB (Plolty Free Subscription only allows 500KB uploads)
        while ((df.memory_usage(index=True).sum() / 1000) > 500):
            df = df.iloc[50:]

        # Create figure with secondary y-axis
        fig = make_subplots(specs=[[{"secondary_y": True}]])

        # Add traces
        fig.add_trace(go.Scatter(x=df['Datetime'], y=df['CO2'], name='CO2'), secondary_y=False)
        fig.add_trace(go.Scatter(x=df['Datetime'], y=df['Temp'], name='Temperature'), secondary_y=True)

        # Add figure title
        fig.update_layout(title_text="Sample Data", plot_bgcolor='rgb(230, 230,230)', showlegend=True)

        #Add Range Slider
        fig.update_layout(
            xaxis=dict(
                rangeselector=dict(
                    buttons=list([
                        dict(count=1,
                             label="1 Hour",
                             step="hour",
                             stepmode="backward"),
                        dict(count=1,
                             label="1 Day",
                             step="day",
                             stepmode="backward"),
                        dict(count=7,
                             label="1 Week",
                             step="day",
                             stepmode="backward"),
                        dict(count=14,
                             label="2 Weeks",
                             step="day",
                             stepmode="backward"),
                        dict(count=1,
                             label="1 Month",
                             step="month",
                             stepmode="todate"),
                        dict(step="all")
                    ])
                ),
                rangeslider=dict(
                    visible=True
                ),
                type="date"
            )
        )

        # Set x-axis title
        fig.update_xaxes(title_text="Date and Time")

        # Set y-axes titles
        fig.update_yaxes(title_text="Temperature", secondary_y=False)
        fig.update_yaxes(title_text="CO2", secondary_y=True)

        # Plot on Chart Studio
        py.plot(fig, filename='sampleData', auto_open=False)

        logger.info("Successful upload to Plotly")
    except (requests.ConnectionError, requests.Timeout):
        logger.error("Internet Connection failure while connecting to Plolty")
    except Exception:
        logger.exception("Error uploading to Plolty")


######################### Raw and Clean Data Savers #####################
#########################################################################
rawFiles = {}
csvFiles = {}

## Creates the Raw Data and Clean Data Folders if non existing
if not os.path.exists(rawDataPath):
    os.makedirs(rawDataPath)
if not os.path.exists(cleanDataPath):
    os.makedirs(cleanDataPath)

## Create a list of paths for each GP in raw and csv
for gp in gpList:
    rawFiles[f"{gp}"] = f"{rawDataPath}/raw{gp}.asc"
    csvFiles[f"{gp}"] = f"{cleanDataPath}/{gp}.csv"

## Takes 2 variables (Unit Number and raw Data) and saves raw data in .asc File
def saveRaw(raw, ID):
    file = rawFiles[str(ID)]
    try:
        with open(file, 'ab+') as f:
            f.write(raw)
            logger.info(f"Save to raw file {file} successful")
    except Exception as error:
        logger.error(f"Error saving to Raw file {file}")
        logger.error(error)

## Takes 2 variables (Unit Number and msg) and saves msg in .csv File
def saveCsv(msg, ID):
    file = csvFiles[str(ID)]
    try:
        with open(file, 'a+') as f:
            writer(f).writerow(msg)
            logger.info(f"Save to CSV {file} successful")
    except Exception as error:
        logger.error(f"Error saving to CSV {file}")
        logger.error(error)

######################### Checks if Port is still Connecte###############
#########################################################################

# Checks the port you specify if disconnected
def check_presence(checkPort):
    currentPorts = [p[0] for p in list(serial.tools.list_ports.comports())]
    if not (checkPort in currentPorts):
        logger.warning(f"Port {checkPort} disconnected!")
        return False
    else:
        logger.info(f"Port {checkPort} connected. Reading...")
        return True

######################### List Serial Ports  ############################
#########################################################################

# Lists All COM Ports (eg: ['/dev/ttyUSB0', '/dev/ttyUSB2'])
def listSerialPorts():
    # return [p[0] for p in list(serial.tools.list_ports.comports())]

    ### To find RS232 Ports specifically ###
    allSerial = [tuple(p) for p in list(serial.tools.list_ports.comports())]
    return [port[0] for port in allSerial if 'USB-RS232 Cable - USB-RS232 Cable' in port[1]]

######################### Serial Port Reader ############################
#########################################################################

# Reads one line from specifid port (eg: port='/dev/ttyUSB3')
def serialReader(port):
    try:
        # opens specified port at specified Baudrate and starts reading
        ser = serial.Serial(port, portBaudrate, timeout=1)
        raw = ser.readline()

        if raw:  # When raw is empty it's false

            # Cleans incoming Data and inserts time
            temp = raw.decode("UTF-8").strip().split(',')[2:6]
            ID = temp[3]

            cleanedLine = list(map(float, temp[0:3]))
            cleanedLine.append(ID)
            cleanedLine.insert(0, datetime.now().strftime("%d/%m/%Y %H:%M:%S"))

            saveRaw(raw, ID)  # saves raw data
            logger.info(f"Read Success from {ID} on port {port}")
            ser.close()  # Closes Port
            return cleanedLine
        else:
            logger.info(f"No Data from port {port}")
            return ""

    except serial.serialutil.SerialException:
        logger.error(f"Failed to Open Port {port}")

    except Exception as error:
        logger.exception(error)
        return ""


############ Checks if port has not been sending data ###################
#########################################################################
portList = {}

# Creates a List of each port and returns TRUE if port exceeds specified 'maxEmptyLines'
def isMaxEmpty(port, isEmpty):
    if port in portList:
        if isEmpty:
            portList[port] += 1
        else:
            portList[port] = 0
    else:
        portList[port] = 0
    return (portList[port] > maxEmptyLines)


############################## Main #####################################
#########################################################################

# Creates an Initial List of Connected Ports
initialPorts = listSerialPorts()

# Uses the RepeatedTimer Class to run 'ploltyUploader' and 'googleDriveUploader' at specified 'uploadTimer' interval in the Background
plotter = RepeatedTimer(uploadTimer, ploltyUploader)
driveUploader = RepeatedTimer(uploadTimer, googleDriveUploader)

try:
    logger.info("I'm ALIVE....")

    # Never Ending Loop the Keeps Checking for new ports
    while True:
        if not initialPorts:
            initialPorts = listSerialPorts()
            logger.info("No Port Connected. Trying to Connect...")
        else:
            for port in initialPorts:
                if check_presence(port):
                    output = serialReader(port)
                    try:
                        if (len(output) > 1):
                            isMaxEmpty(port, False)
                            saveCsv(output, output[4])
                            googleUploader(output, output[4])  # do this immediatly
                        elif isMaxEmpty(port, True):
                            logger.warning(f"Port {port} stopped sending Data")
                    except Exception as error:
                        logger.error(error)
        logger.debug("------------------------------------------------------")
        initialPorts = listSerialPorts()
        time.sleep(sleepTime)

except KeyboardInterrupt:
    logger.info("Exiting Script - Remember Me!")
except Exception as error:
    logger.exception(error)
finally:
    # Stops the Background Threads or else they'll keep running or prevent new ones from starting
    plotter.stop()
    driveUploader.stop()