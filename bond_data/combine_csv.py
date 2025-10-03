import os
import pandas as pd

def combine_csv_files(input_directory, output_filename="combined_data.csv"):

    all_files = [os.path.join(input_directory, f) for f in os.listdir(input_directory) if f.endswith('.csv')]

    # Create an empty list to store DataFrames
    df_list = []

    # Read each CSV file and append its DataFrame to the list
    for file in all_files:
        try:
            df = pd.read_csv(file)
            df_list.append(df)
        except Exception as e:
            print(f"Error reading {file}: {e}")

    if not df_list:
        print("No valid CSV files were read.")
        return

    # Concatenate all DataFrames in the list
    combined_df = pd.concat(df_list, ignore_index=True)

    # Save the combined DataFrame to a new CSV file
    try:
        combined_df.to_csv(input_directory + "\\" + output_filename, index=False)
        print(f"Successfully combined {len(all_files)} CSV files into {output_filename}")
    except Exception as e:
        print(f"Error saving combined data to {output_filename}: {e}")

if __name__ == "__main__":
    print("starting up")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    combine_csv_files(input_directory=script_dir)