import json
import os
from utilities import *
import datetime 
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

#store the most recent on the run bonds
current_otr_bonds = {}

script_dir = os.path.dirname(os.path.abspath(__file__))

def get_current_bonds()->pd.DataFrame:

    file_path = r"bond_data\combined_data.csv"
    data = pd.read_csv(file_path)
    #convert the date columns actual date
    data["Maturity Date"] = pd.to_datetime(data['Maturity Date'])
    data["Issue Date"] = pd.to_datetime(data["Issue Date"])
    #we will use the auction date to determine when to roll our bonds
    data["Auction Date"] = pd.to_datetime(data["Auction Date"])
    data["Interest Payment Frequency"] = data["Interest Payment Frequency"].apply(trans_pay_freq_to_int)
    data["Interest Rate"] = data["Interest Rate"].str.replace('%', '', regex=False).pipe(pd.to_numeric, errors='coerce') / 100 
    #save_pd_to_file(data, "bond_data_transformed.csv")
    return data

def get_historical_prices(file_name : str)->pd.DataFrame:    
    file_path = script_dir + "\\" + file_name
    data = pd.read_csv(file_path)
    data["Unnamed: 0"] = pd.to_datetime(data["Unnamed: 0"])
    data.rename(columns={"Unnamed: 0" : "Date"}, inplace=True)
    return data

def create_time_series_data(tenor:str, hist_yields_file : str)->pd.DataFrame:
    current_bonds = get_current_bonds()
    bond_data = current_bonds[current_bonds["Security Term"] == tenor]
    
    #work backwards from our set of ref data within our bonds and figure out backwards the On The Run Treasuries.
    bond_data.sort_values(by="Auction Date", ascending=False, inplace=True)
    bond_prices = get_historical_prices(hist_yields_file)
    #get rid of the first row since it does not contain much information for use 
    bond_prices.drop(0, inplace=True)
    #save_pd_to_file(bond_data, "selected_bonds.csv")
    df_list = []
    last_auct_date = None

    for bond in bond_data.values:
        bond_cusip = bond[0] + " GOVT"
        if bond_cusip in bond_prices.columns:
            filtered_data = pd.DataFrame()
            bond_auct_date = bond[4] 
            hist_bond_prices = bond_prices[["Date", bond_cusip]].copy() 

            if last_auct_date == None:
                filtered_data = hist_bond_prices.loc[hist_bond_prices["Date"] >= bond_auct_date]
                if not filtered_data.empty:
                    #store the latest on the run treasury and it's yield
                    last_yield = filtered_data.loc[(filtered_data["Date"] == filtered_data["Date"].max())]
                    current_otr_bonds[tenor] = (np.append(bond, float(last_yield.iloc[0][bond_cusip])))
                            
            else:
                filtered_data = hist_bond_prices.loc[(hist_bond_prices["Date"] >= bond_auct_date) & (hist_bond_prices["Date"] <= last_auct_date)]
                
            filtered_data.rename(columns={bond_cusip : tenor}, inplace=True)
            if not filtered_data.empty:
                #adjust for rolling of bonds from otr (on the run) to ofr (off the run)
                if len(df_list) != 0:
                    #compute the spread of the ofr and the otr when they transtion by taking the diff of the current on the run and the new issuance at teh new issuance auction date
                    ofr_data = filtered_data.loc[(filtered_data["Date"] == last_auct_date)]
                    ofr_yield = float(ofr_data[tenor].iloc[0])

                    last_filt_df = df_list[-1]
                    otr_data = last_filt_df.loc[(last_filt_df["Date"] == last_auct_date)]
                    otr_data = float(otr_data[tenor].iloc[0])

                    diff_yield = otr_data - ofr_yield

                    last_filt_df.loc[(last_filt_df["Date"] == last_auct_date), tenor] = otr_data + diff_yield
                    # remove the prior otr data point to prevent data overlap and redunancy
                    filtered_data = filtered_data.drop(index=filtered_data.index[-1])

                last_auct_date = bond_auct_date
                df_list.append(filtered_data)
                

    final_data = pd.concat(df_list, ignore_index=False)
    final_data[tenor] = pd.to_numeric(final_data[tenor])
    final_data.sort_values(by="Date", ascending=True, inplace=True)
    return final_data

def construct_bond_prices(list_of_tenor :list[str], prices : str)->pd.DataFrame:
    bond_df_list = []
    for maturity in list_of_tenor:
        tenor = translate_tenor(maturity[-1])
        length = maturity[:-1]
        bond_mat_str = length+"-"+tenor
        bond_df = create_time_series_data(bond_mat_str, prices)
        bond_df_list.append(bond_df.set_index("Date"))
        # save_pd_to_file(bond_df, "bond_data_" + maturity + ".csv")

    final_data = pd.concat(bond_df_list, axis=1, join="inner", ignore_index=False)
    return final_data

def analyze_butterflies(list_of_tenor : list[str], prices : str, lookback_days: int, analytics : Analytics,  window_size : int=30)->json:
    bond_df_list = []
    bond_list_str = []
    butterfly_str = "".join(list_of_tenor)
    for maturity in list_of_tenor:
        tenor = translate_tenor(maturity[-1])
        length = maturity[:-1]
        bond_mat_str = length+"-"+tenor
        bond_df = create_time_series_data(bond_mat_str, prices)
        bond_list_str.append(bond_mat_str)
        bond_df_list.append(bond_df.set_index("Date"))
        #save_pd_to_file(bond_df, "bond_data_" + maturity + ".csv")

    final_data  = pd.concat(bond_df_list, axis=1, join="inner")
    
    weighting = compute_weights(bond_list_str, analytics, final_data, current_otr_bonds)
    weight_columns = {"Left Wing" : [weighting[0]], "Body" : [weighting[1]], "Right Wing" : [weighting[2]]}
    weighting_map = pd.DataFrame(weight_columns) 

    final_data[butterfly_str] = -final_data[final_data.columns[0]] + 2*final_data[final_data.columns[1]] + -final_data[final_data.columns[2]]
    #scale butterfly to quote it in bips
    final_data[butterfly_str] = final_data[butterfly_str] * 100

    #compute Z Score 
    mean = final_data[butterfly_str].mean()
    std_dev = final_data[butterfly_str].std()
    final_data["Z_Score_" + butterfly_str] = (final_data[butterfly_str] - mean)/ std_dev
    
    #compute rolling Window
    rolling_window_key = str(window_size)+"D-Moving-AVG-"+ butterfly_str
    final_data[rolling_window_key] = final_data[butterfly_str].rolling(window_size).mean()
    final_data["Rolling-Win-Diff"] = final_data[butterfly_str] - final_data[rolling_window_key] 

    final_data.sort_values(by="Date",ascending=False, inplace=True)

    final_look_back_data = final_data.head(lookback_days)

    #plot the different data
    plot_pd_df(final_look_back_data, "Date", butterfly_str, rolling_window_key)

    plot_heat_map(final_look_back_data)
    plot_weightings_map(weighting_map)
    save_fig_to_pdf()
    plt.show()
    
    final_results = {"Weighting" : weighting, "Analysis" : final_data }
    return final_results

if __name__ == "__main__":

    # bond_df = create_time_series_data("5-Year", "yields.csv")
    # save_pd_to_file(bond_df, "bond_data_5-Year.csv")

    list_of_tenors = ["2y", "3y", "5y", "7y", "10y", "20y", "30y"]
    # list_of_tenors = ["2y", "3y", "5y"]
    bond_data = construct_bond_prices(list_of_tenors, "yields.csv")
    save_pd_to_file(bond_data, "hist_bond_data.csv")


    # butterfly = ["5y", "10y", "30y"]
    # results = analyze_butterflies(butterfly, "yields.csv", 30, Analytics.pca)
    # input("Press Enter to end program...")



  
