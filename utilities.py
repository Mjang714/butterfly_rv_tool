from bond_math import *
from enum import Enum
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
import os
import pandas as pd
import seaborn as sns
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA

script_dir = os.path.dirname(os.path.abspath(__file__))

class Analytics(Enum):
    fifty_fifty = 1
    regression = 2
    pca = 3
    duration_neutral = 4

#this fucntion is used to convert a string into Analyitics Enum if it is not one of the existing ones it will default to duration nuetral
def trans_str_to_enum_anal(pca_str:str)->Analytics:
    key = pca_str.upper()
    match key:
        case"50-50":
            return Analytics.fifty_fifty
        case"REGRESSION":
            return Analytics.regression
        case "PCA":
            return Analytics.pca
        case "DURATION":
            return Analytics.duration_neutral
        case _:
            return Analytics.duration_neutral



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
    return data

def get_historical_prices(file_name : str)->pd.DataFrame:    
    file_path = script_dir + "\\" + file_name
    data = pd.read_csv(file_path)
    data["Unnamed: 0"] = pd.to_datetime(data["Unnamed: 0"])
    data.rename(columns={"Unnamed: 0" : "Date"}, inplace=True)
    return data

def save_pd_to_file(data : pd.DataFrame, file_name :str):
    data.to_csv(script_dir+"\\" + file_name)

def compute_weights(bond_list : list[str], methodology : Analytics, data : pd.DataFrame, curr_otr_bonds:list)->list[float]:
    list_of_duration = []
    list_of_price = []
    for bond in curr_otr_bonds:
        bond_duration = macaulay_duration(100, bond[8], bond[9]/100, int(bond[2].split("-")[0]), bond[7])
        list_of_duration.append(bond_duration)
        bond_price = calculate_bond_price(int(bond[2].split("-")[0]), bond[9]/100, bond[8], bond[7])
        list_of_price.append(bond_price)


    match methodology:
        case Analytics.fifty_fifty:
            A = np.array([[list_of_duration[0], list_of_duration[2]],[list_of_duration[0], -list_of_duration[2]]])
            b = np.array([-2*list_of_duration[1], 0])
            results = np.linalg.solve(A, b)
            return [results[0], 2, results[1]]
        case Analytics.regression:
            cov_matrix = data.corr()
            A = np.array([[list_of_duration[0], list_of_duration[2]],[list_of_duration[0], -cov_matrix.loc[bond_list[0], bond_list[2]]*list_of_duration[2]]])
            b = np.array([-2*list_of_duration[1], 0])
            results = np.linalg.solve(A, b)
            return [results[0], 2, results[1]]
        case Analytics.duration_neutral:
            A = np.array([[list_of_duration[0], list_of_duration[2]],[list_of_price[0], list_of_price[2]]])
            b = np.array([-2*list_of_duration[1], -2*list_of_price[1]])
            results = np.linalg.solve(A, b)
            return [results[0], 2, results[1]]
        case Analytics.pca:
            scaler = StandardScaler()
            #sclae the inputs to prevent one of the inputs from dominating
            scaled_inputs = scaler.fit_transform(data)
            pca = PCA(n_components=3)
            #fit the data and return the third component 
            pca.fit_transform(scaled_inputs)
            return pca.components_[2, :]*(2/pca.components_[2, :][1])
        case _:  
            return [-1, 1, -1]
        
def translate_tenor(tenor : str)->str:
    match tenor:
        case"Y"|"y":
            return "Year"
        case"M"|"m":
            return "Month"
        case"W"|"w":
            return "Week"
        case"D"|"d":
            return "Day"
        case"Year":
            return "y"
        case"Month":
            return "m"
        case"Week":
            return "w"
        case"Day":
            return "d"
        case _:
            return ""

#this function translate the payment freq of the bond into an integer value 
def trans_pay_freq_to_int(payment_freq_str:str)->int:
    match payment_freq_str:
        case "Annual":
            return 1
        case "Semi-Annual":
            return 2
        case "Quarterly":
            return 4
        case _:
            return 1          

def plot_pd_df(data_frame: pd.DataFrame, x_data_str : str, y1_data_str:str, y2_data_str:str):
    sns.set_theme(style="whitegrid") 

    plt.figure(1, figsize=(12, 6))
    sns.lineplot(data=data_frame, x=x_data_str, y=y1_data_str, label=y1_data_str, color='blue')
    sns.lineplot(data=data_frame, x=x_data_str, y=y2_data_str, label=y2_data_str, color='red', linestyle='--')

    plt.xlabel('Date')
    plt.ylabel('Yield')
    plt.title('Share Highest Price Over Time')
    

def plot_heat_map(data_frame: pd.DataFrame, Title:str):
    plt.figure(figsize=(12, 30))
    # plt.figure(2)
    map = sns.heatmap(data_frame, annot=True,  xticklabels=True, yticklabels=True, cmap="crest", fmt=".2f")
    ticklabels = [data_frame.index[int(tick)].strftime('%Y-%m-%d') for tick in map.get_yticks()]
    map.set_yticklabels(ticklabels)
    plt.title(Title)

def plot_df(data_frame: pd.DataFrame, Title:str)   : 
    plt.figure(figsize=(12, 30))


def plot_weightings_map(butterfly_weightings: map):
    plt.figure()
    y_labels = []
    wieghting_list= []
    for butterfly, weightings in butterfly_weightings.items():
        y_labels.append(butterfly)
        wieghting_list.append(weightings)
    weighting_df = pd.concat(wieghting_list)
    weighting_heat_map = sns.heatmap(weighting_df, annot=True,  xticklabels=True, yticklabels=True, cmap="crest", fmt=".2f")
    weighting_heat_map.set_yticklabels(y_labels)
    plt.title('Butterfly Weights')

def save_fig_to_pdf():
    figure_numbers = plt.get_fignums()
    figures = [plt.figure(num) for num in figure_numbers]
    with PdfPages("report.pdf") as pdf:
        for fig in figures:
            pdf.savefig(fig)