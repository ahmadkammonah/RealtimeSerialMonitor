# RealtimeSerialPlotter
Python script to detect serial ports, reads and cleans the data, and uploads it to Google Drive and Plotly for real-time plotting.

## Run command
It's preffered to run this script using 'gnome-terminal -- python3 -i main.py' (or any other terminal command you prefer) to be able to monitor the log and exit cleanly when needed. 

## Setup 
There are a few things that need to be setup before running the script on your system. 

### Installing required packages
1. Use 'pip3 install -r requirements.txt' in command terminal (Linux) to install the required packages for this project.  

### Setting up Google Service account 
1. Creating Google Service Account
The Google service account represent a non-human user that will be authenticated to access and edit your drive and spreadsheets for saving and plotting data. [Follow this Google Documentation](https://support.google.com/a/answer/7378726?hl=en) (Skip Step 3 as this is not an APP)
   - **For step 2Search for and enable _Google Drive API_ and _Google Sheets API_**.
   - **IMPORTANT:** Assign the service account an **Editor Role** to be able to edit your drive and spreadsheets.
   - Make sure you save the private key JSON file created in Step 4 of Google's Documentation and refer to it in _main.py_. 
 
2. Adding Servcie account to your spreadhsheet.  
   1. Open the private key JSON file created in the previous step and copy the _client_email_ field. 
   2. Share your spreadsheet with the _client_email_ with editing access ([similar to how you'd share i with anyone](https://support.google.com/docs/answer/9331169?hl=en)).
   
### Setting Up Plotly Account 
1. Create [Chart Studio Account](https://plotly.com/chart-studio/). 
2. Create a new chart and paste the chart's title in _plotyChartTitle_ field in _main.py_ file
3. Find your API Settings [here](https://chart-studio.plotly.com/settings/api#/) and click on _Regenrate Key_
4. Paste your username and API key in the _main.py_ file. 
