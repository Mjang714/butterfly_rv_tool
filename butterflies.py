import json
from utilities import *
import datetime 
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import tkinter as tk

#store the most recent on the run bonds
current_otr_bonds = {}

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

def analyze_butterflies(list_of_butterflies : list[str], prices : str, lookback_days: int, analytics : Analytics)->json:

    list_of_tenors = ["2y", "3y", "5y", "7y", "10y", "20y", "30y"]
    bond_data = construct_bond_prices(list_of_tenors, prices)
    save_pd_to_file(bond_data, "hist_bond_data.csv")
    butterfly_heatmap_unweighted = pd.DataFrame()
    butterfly_heatmap_weighted = pd.DataFrame()
    butterfly_weighting = {}

    for butterfly in list_of_butterflies:   
        tenor_list = butterfly.split('y')
        tenor_list = tenor_list[:-1]
        bond_list_str = []
        curr_otr_bond_list = []
        for tenor in tenor_list:
            bond_list_str.append(tenor + "y")
            curr_otr_bond_list.append(current_otr_bonds[tenor + "-Year"])

        weighting = compute_weights(bond_list_str, analytics, bond_data, curr_otr_bond_list)
        weight_columns = {"Left Wing" : [weighting[0]], "Body" : [weighting[1]], "Right Wing" : [weighting[2]]}
        butterfly_weighting[butterfly] = pd.DataFrame(weight_columns) 

        butterfly_heatmap_unweighted[butterfly] = (-bond_data[tenor_list[0] + "-Year"] + 2*bond_data[tenor_list[1] + "-Year"] - bond_data[tenor_list[2] + "-Year"])*100
        butterfly_heatmap_weighted[butterfly] = (-bond_data[tenor_list[0] + "-Year"]*weighting[0] + bond_data[tenor_list[1] + "-Year"]*weighting[1] - bond_data[tenor_list[2] + "-Year"]*weighting[2])
        print()
        # #compute Z Score 
        # mean = final_data[but  terfly_str].mean()
        # std_dev = final_data[butterfly_str].std()
        # final_data["Z_Score_" + butterfly_str] = (final_data[butterfly_str] - mean)/ std_dev
        
        # #compute rolling Window
        # rolling_window_key = str(window_size)+"D-Moving-AVG-"+ butterfly_str
        # final_data[rolling_window_key] = final_data[butterfly_str].rolling(window_size).mean()
        # final_data["Rolling-Win-Diff"] = final_data[butterfly_str] - final_data[rolling_window_key] 
    # butterfly_heatmap = pd.concat([butterfly_heatmap_unweighted, butterfly_heatmap_weighted], axis=1, join="inner", ignore_index=False)
    # butterfly_heatmap.sort_values(by="Date",ascending=False, inplace=True)
    # final_look_back_data = butterfly_heatmap.head(lookback_days)
    butterfly_heatmap_unweighted["cheapest"] = butterfly_heatmap_unweighted.min(axis=1)
    butterfly_heatmap_unweighted["richest"] = butterfly_heatmap_unweighted.max(axis=1)
    butterfly_heatmap_unweighted.sort_values(by="Date",ascending=False, inplace=True)
    butterfly_heatmap_unweighted = butterfly_heatmap_unweighted.head(lookback_days)

    butterfly_heatmap_weighted["cheapest"] = butterfly_heatmap_weighted.min(axis=1)
    butterfly_heatmap_weighted["richest"] = butterfly_heatmap_weighted.max(axis=1)
    butterfly_heatmap_weighted.sort_values(by="Date",ascending=False, inplace=True)
    butterfly_heatmap_weighted = butterfly_heatmap_weighted.head(lookback_days)
    #plot the different data
    #plot_pd_df(final_look_back_data, "Date", butterfly_str, rolling_window_key)

    plot_heat_map(butterfly_heatmap_unweighted, "Unweighted Heat Map")
    plot_heat_map(butterfly_heatmap_weighted, "Weighted Heat Map")
    plot_weightings_map(butterfly_weighting)
    # save_fig_to_pdf()
    plt.show()
    
    final_results = {"Weighting" : weighting}
    return final_results


def get_selected_items(listbox):
    selected_indices = listbox.curselection()
    selected_items = [listbox.get(i) for i in selected_indices]
    return selected_items

def create_multi_select_tkinter():
    #root is the window
    root = tk.Tk()
    root.geometry("500x250")
    root.title("Butterfly Relative Value Analysis")

    butterfly_options = ["2y3y5y", "2y10y30y", "2y5y10y", "2y20y30y", "3y5y7y", "3y7y10y","3y10y20y","3y20y30y", "5y7y10y","5y10y20y", "5y10y30y", "5y20y30y"]
    
    listbox = tk.Listbox(root, selectmode=tk.MULTIPLE)
    for item in butterfly_options:
        listbox.insert(tk.END, item)

    selected_rolling_window = tk.StringVar(root)
    rolling_window_length = [10,20,30,45,60]
    selected_rolling_window.set(rolling_window_length[2])
    dropdown = tk.OptionMenu(root, selected_rolling_window, *rolling_window_length)

    selected_analysis_window = tk.StringVar(root)
    pca_options = ["50-50", "Regression", "Duration", "PCA"]
    selected_analysis_window.set(pca_options[2])
    dropdown_pca = tk.OptionMenu(root, selected_analysis_window, *pca_options)

    def run_analysis():
        butterflies_selected = get_selected_items(listbox)
        roll_wind = int(selected_rolling_window.get())
        weighting_analytics = trans_str_to_enum_anal(selected_analysis_window.get())
        print("You selected:", butterflies_selected)
        analyze_butterflies(butterflies_selected, "yields.csv", roll_wind, weighting_analytics)

    select_button = tk.Button(root, text="Analyze Butterflys", command=run_analysis)
    select_button.pack(side=tk.BOTTOM, pady=10)
    
    listbox.pack(side=tk.LEFT)
    dropdown_pca.pack(side=tk.LEFT, pady=20, padx=30)
    dropdown.pack(side=tk.LEFT, pady=20, padx=30)

    root.mainloop()



if __name__ == "__main__":

    create_multi_select_tkinter()



  
