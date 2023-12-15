import requests
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

def fetch_data(station_code, start_date, end_date):
    url = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
    
    params = {
        "station": station_code,
        "data": [
            "vsby", "skyc1", "skyc2", "skyc3",
            "skyl1", "skyl2", "skyl3"
        ],
        "year1": start_date.year,
        "month1": start_date.month,
        "day1": start_date.day,
        "year2": end_date.year,
        "month2": end_date.month,
        "day2": end_date.day,
        "tz": "Etc/UTC",
        "format": "onlycomma",
        "latlon": "no",
        "elev": "no",
        "missing": "M",
        "trace": "T",
        "direct": "no",
        "report_type": 3
    }

    response = requests.get(url, params=params)
    
    # Check if the request was successful
    if response.status_code == 200:
        return response.text
    else:
        raise Exception(f"Failed to fetch data for station {station_code}. Status code: {response.status_code}")


def parse_csv_to_dataframe(csv_data):
    # Use StringIO to convert the CSV string into a file-like object
    from io import StringIO
    csv_file = StringIO(csv_data)
    
    # Load the CSV data into a Pandas DataFrame
    df = pd.read_csv(csv_file)

    # Replace "M" with NaN in the 'vsby' column
    df['vsby'] = df['vsby'].replace('M', pd.NA)
     
    #Ensure that observation time column is in datetime format
    df.index = pd.to_datetime(df['valid'])
    
    return df

def save_to_csv(df, station_code, file_suffix=''):
    # Save the DataFrame to a CSV file
    df.to_csv(f"csv/{station_code}_data{file_suffix}.csv", index=False)
    

def find_ceiling(df):
    # Define the columns to check for "BKN" or "OVC"
    skyc_columns = ["skyc1", "skyc2", "skyc3"]
    skyl_columns = ["skyl1", "skyl2", "skyl3"]

    for index, row in df.iterrows():
        ceiling_found = False
        for i, skyc_column in enumerate(skyc_columns):
            if row[skyc_column] == "BKN" or row[skyc_column] == "OVC" or row[skyc_column] == "VV":
                # Convert the value to numeric before assignment
                df.at[index, 'ceiling'] = pd.to_numeric(row[skyl_columns[i]], errors='coerce')
                ceiling_found = True
                break  # Stop searching for "BKN" or "OVC" in other columns

        if not ceiling_found:
            # If no ceiling is found, set the default value to 99999
            df.at[index, 'ceiling'] = 99999

    # Ensure 'ceiling' column has an integer data type
    df['ceiling'] = pd.to_numeric(df['ceiling'], errors='coerce').fillna(99999).astype(int)

    return df

#def save_to_csv(df, station_code):
#    # Save the DataFrame to a CSV file
#    df.to_csv(f"csv/{station_code}_data.csv", index=False)

def calculate_flight_rules(df):
    # Convert 'ceiling' and 'vsby' columns to numeric
    df['ceiling'] = pd.to_numeric(df['ceiling'], errors='coerce')
    df['vsby'] = pd.to_numeric(df['vsby'], errors='coerce')

    # Create new columns for aviation flight rule categories
    df['VFR'] = (df['ceiling'] >= 2500) & (df['vsby'] >= 6)
    df['MVFR'] = (
        ((df['ceiling'] >= 1000) & (df['ceiling'] < 2500) & (df['vsby'] >= 3) & (df['vsby'] <= 5)) |
        ((df['ceiling'] >= 1000) & (df['ceiling'] < 2500) & (df['vsby'] >= 3)) |
        ((df['ceiling'] >= 2500) & (df['vsby'] >= 3) & (df['vsby'] <= 5)))
    df['IFR'] = (
        ((df['ceiling'] >= 400) & (df['ceiling'] < 1000) & (df['vsby'] >= 1) & (df['vsby'] < 3)) |
        ((df['ceiling'] >= 400) & (df['ceiling'] < 1000) & (df['vsby'] >= 1)) |
        ((df['ceiling'] >= 1000) & (df['vsby'] >= 1) & (df['vsby'] < 3)))
    df['LIFR'] = (df['ceiling'] < 400) | (df['vsby'] < 1)

    return df

def plot_flight_category_occurrences(combined_df, category_name):
    # Count the total occurrences of "True" in the specified flight category for each station
    category_counts = combined_df.groupby('Station')[category_name].sum()

    # Calculate the total number of rows (hours) for each station
    total_hours = combined_df.groupby('Station').size()

    # Calculate the average number of hours per year for each station
    avg_hours_per_year = (category_counts / total_hours) * 365.25 * 24

    # Plot a bar chart with larger size and higher DPI
    plt.figure(figsize=(16, 8), dpi=200)

    # Set a colormap based on the count values
    colors = plt.cm.viridis(category_counts / category_counts.max())

    plt.bar(category_counts.index, avg_hours_per_year, color=colors)
    plt.xlabel('Station', fontsize=14)  # Increase font size
    plt.ylabel(f'Average {category_name} Hours per Year', fontsize=14)  # Increase font size
    plt.title(f'Average {category_name} Hours per Year for Each Station', fontsize=16)  # Increase font size

    # Rotate station name labels to prevent overlapping
    plt.xticks(rotation=45, ha='right', fontsize=12)  # Increase font size

    # Save the plot to a .png file
    plt.savefig(f'images/average_{category_name}_hours_per_year.png', bbox_inches='tight')  # Adjust layout to include labels
    plt.close()

def plot_subvfr_frequency_by_hour(combined_df):
    # Filter rows based on sub-VFR conditions
    subvfr_df = combined_df[~combined_df['VFR']]

    # Convert the 'valid' column to datetime (if not already)
    subvfr_df['valid'] = pd.to_datetime(subvfr_df['valid'], errors='coerce')

    # Extract hour of the day from the 'valid' column
    subvfr_df['hour'] = subvfr_df['valid'].dt.hour

    # Use a single color for all bars
    bar_color = 'tab:orange'  # Change color to orange for sub-VFR conditions

    # Create a separate figure for each station
    for station in subvfr_df['Station'].unique():
        station_df = subvfr_df[subvfr_df['Station'] == station]

        # Create subplots for each month
        fig, axes = plt.subplots(3, 4, figsize=(20, 12), dpi=100, sharex=True, sharey=True)
        fig.suptitle(f'Sub-VFR Frequency by Hour - {station}', fontsize=24)

        max_percentage = 0  # Initialize max_percentage to 0

        for month, ax in zip(range(1, 13), axes.flatten()):
            month_df = station_df[station_df['month'] == month]
            if not month_df.empty:  # Check if the dataframe is not empty

                for hour in range(24):
                    # Calculate total number of observations for each month and hour
                    station_hour_month_df = combined_df[
                    (combined_df['Station'] == station) &
                    (combined_df['hour'] == hour) &
                    (combined_df['valid'].dt.month == month)
                    ]

                    total_hours = len(station_hour_month_df)
                    # Plot sub-VFR frequency by hour for each station
                    hour_df = month_df[month_df['hour'] == hour]
                    percentage_data = (hour_df['hour'].value_counts(sort=False) / total_hours) * 100
                    ax.bar(percentage_data.index, percentage_data, color=bar_color, alpha=0.7, align='center')
                    ax.set_title(month_df['valid'].dt.strftime('%B').iloc[0])  # Use month names
                    ax.set_xlabel('Hour of Day (UTC)', fontsize=12)
                    ax.set_ylabel('%', fontsize=12)
                    ax.set_xticks(range(24))
                    ax.set_xticklabels([str(hour) for hour in range(24)], rotation=90, ha='center')  # Rotate x-axis labels

                    # Dynamically set y-axis ticks based on maximum percentage over all months/subplots
                   # max_percentage = max(max_percentage, int(percentage_data.max(skipna=True)))

       # for ax in axes.flatten():
       #     y_ticks = range(0, max_percentage + 1, 1)
        #    ax.set_yticks(y_ticks)

        plt.tight_layout(rect=[0, 0.03, 1, 0.95])

        plt.savefig(f'images/subvfr_frequency_by_hour_{station}.png', bbox_inches='tight')
        plt.close()

def plot_flight_category_frequency_by_hour(combined_df, flight_category):
    # Filter rows based on the specified flight category
    category_df = combined_df[combined_df[flight_category]]

    # Convert the 'valid' column to datetime (if not already)
    category_df['valid'] = pd.to_datetime(category_df['valid'], errors='coerce')

    # Extract hour of the day from the 'valid' column
    category_df['hour'] = category_df['valid'].dt.hour

    # Use a single color for all bars
    bar_color = 'tab:blue'

    # Create a separate figure for each station
    for station in category_df['Station'].unique():
        station_df = category_df[category_df['Station'] == station]

        # Create subplots for each month
        fig, axes = plt.subplots(3, 4, figsize=(20, 12), dpi=100, sharex=True, sharey=True)
        fig.suptitle(f'{flight_category} Frequency by Hour - {station}', fontsize=24)

        max_percentage = 0  # Initialize max_percentage to 0

        for month, ax in zip(range(1, 13), axes.flatten()):
            month_df = station_df[station_df['month'] == month]
            if not month_df.empty:  # Check if the dataframe is not empty

                for hour in range(24):
                    # Calculate total number of observations for each month and hour
                    station_hour_month_df = combined_df[
                    (combined_df['Station'] == station) &
                    (combined_df['hour'] == hour) &
                    (combined_df['valid'].dt.month == month)
                    ]

                    total_hours = len(station_hour_month_df)

                    # Plot flight category frequency by hour for each station
                    hour_df = month_df[month_df['hour'] == hour]
                    percentage_data = (hour_df['hour'].value_counts(sort=False) / total_hours) * 100
                    ax.bar(percentage_data.index, percentage_data, color=bar_color, alpha=0.7, align='center')
                    ax.set_title(month_df['valid'].dt.strftime('%B').iloc[0])  # Use month names
                    ax.set_xlabel('Hour of Day (UTC)', fontsize=12)
                    ax.set_ylabel('%', fontsize=12)
                    ax.set_xticks(range(24))
                    ax.set_xticklabels([str(hour) for hour in range(24)], rotation=90, ha='center')  # Rotate x-axis labels

                    # Dynamically set y-axis ticks based on maximum percentage over all months/subplots
                    #max_percentage = max(max_percentage, int(percentage_data.max(skipna=True)))

        #for ax in axes.flatten():
        ##    y_ticks = range(0, max_percentage + 1, 1)
         #   ax.set_yticks(y_ticks)

        plt.tight_layout(rect=[0, 0.03, 1, 0.95])

        plt.savefig(f'images/{flight_category.lower()}_frequency_by_hour_{station}.png', bbox_inches='tight')
        plt.close()


def combine_dataframes(station_dfs, station_codes):
    # Add a 'Station' column to each DataFrame
    for i, df in enumerate(station_dfs):
        df['Station'] = station_codes[i]

    # Concatenate the DataFrames into one big DataFrame
    combined_df = pd.concat(station_dfs, ignore_index=True)

    return combined_df

if __name__ == "__main__":
    #####ICAO codes for the stations you are interested in
    station_codes =["CYEG", "CYYC", "EHAM", "EHBK", "EHEH",
        "EHRD", "LFPO", "LFST", "TKPK", "KMLB",
        "KMCN", "KVQQ", "CYMX", "KMZJ", "KSLN",
        "KINT", "KLCQ"]
    
    #####Start and end time for the climatological period of interest
    start_date = pd.to_datetime("2013-01-01")
    end_date = pd.to_datetime("2022-12-31")

    station_dfs = []

    for station_code in station_codes:
        try:
            # Fetch data from the URL for each station
            csv_data = fetch_data(station_code, start_date, end_date)

            # Save the raw data to a CSV file
            save_to_csv(parse_csv_to_dataframe(csv_data), station_code + '_raw')

            # Parse CSV data into a Pandas DataFrame
            df = parse_csv_to_dataframe(csv_data)

            # Convert 'vsby' column to numeric (in case it's not already)
            df['vsby'] = pd.to_numeric(df['vsby'], errors='coerce')

            # Find the ceiling for each row
            df = find_ceiling(df)

            # Calculate aviation flight rule categories
            df = calculate_flight_rules(df)

            # Save the modified DataFrame to a new CSV file for each station
            save_to_csv(df, station_code)

            # Append the DataFrame to the list
            station_dfs.append(df)

            # Display information about the station and the modified DataFrame
            print(f"\nStation: {station_code}")
            print(df.head())

        except Exception as e:
            print(f"Error processing data for station {station_code}: {e}")

    # Combine the DataFrames for all stations into one big DataFrame
    combined_df = combine_dataframes(station_dfs, station_codes)

    # Ensure 'valid' column is datetime type
    combined_df['valid'] = pd.to_datetime(combined_df['valid'], errors='coerce')

    # Create a new column 'month' to store the month information
    combined_df['month'] = combined_df['valid'].dt.month

    # Extract hour of the day from the 'valid' column
    combined_df['hour'] = combined_df['valid'].dt.hour

    print(combined_df)


    # Plot and save the total number of occurrences of "True" in the flight categories for each station
    flight_categories = ['VFR', 'MVFR', 'IFR', 'LIFR']
    for category_name in flight_categories:
        plot_flight_category_occurrences(combined_df, category_name)

    # Plot the frequency of sub-VFR conditions by hour and month for each station
    plot_subvfr_frequency_by_hour(combined_df)

    # Plot the frequency of MVFR conditions by hour for each station
    plot_flight_category_frequency_by_hour(combined_df, 'MVFR')

    # Plot the frequency of IFR conditions by hour for each station
    plot_flight_category_frequency_by_hour(combined_df, 'IFR')

    # Plot the frequency of LIFR conditions by hour for each station
    plot_flight_category_frequency_by_hour(combined_df, 'LIFR')