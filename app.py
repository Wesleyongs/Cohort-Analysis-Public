import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib as mpl
import glob
import os
import sys
import plotly as py
from plotly.offline import download_plotlyjs, init_notebook_mode, iplot
from plotly.graph_objs import *
import plotly.graph_objs as go
import plotly
import plotly.express as px
import xlsxwriter
import base64
from io import BytesIO
import os

###########
# heading #
###########
st.set_page_config(layout="wide")
st.write("""
# Online Corhort Analysis Generator
This app tracks **cohort analysis** for any given period - This a popular analysis many e-commerce company use to track customer retention rates  
Ensure input **csv** has the following columns  
> 1. month  
> 2. order_id  
> 3. customer_id      

Created by [Wesley Ong](https://wesleyongs.com/).
""")

################
# Upload Files #
################

# SG
uploaded_file = st.file_uploader('Upload CSV file', type="csv")
    
if uploaded_file is not None:
    df = pd.read_csv(uploaded_file,
                   parse_dates=['month'])
    title = "Your"
else:    
    df = pd.read_csv('dummy_data.csv',
                    parse_dates=['month'])
    title = "Dummy"

# Download table 
def get_table_download_link(df):
    """Generates a link allowing the data in a given panda dataframe to be downloaded
    in:  dataframe
    out: href string
    """
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()  # some strings <-> bytes conversions necessary here
    href = f'<a href="data:file/csv;base64,{b64}">Download csv file</a>'

def show_cohort_analysis(df, region):    
    
    st.title(title+" Results")
    col1,col2 = st.beta_columns((1,1))

    ########################
    ##   Data Wraggling   ##
    ########################

    df['OrderPeriod'] = df.month.apply(lambda x: x.strftime('%Y-%m'))
    df.set_index('customer_id', inplace=True)
    df['CohortGroup'] = df.groupby(level=0)['month'].min().apply(lambda x: x.strftime('%Y-%m'))
    df.reset_index(inplace=True)
    grouped = df.groupby(['CohortGroup', 'OrderPeriod'])
    cohorts = grouped.agg({'customer_id': pd.Series.nunique,
                        'order_id': pd.Series.nunique})
    cohorts.rename(columns={'customer_id': 'TotalUsers',
                            'order_id': 'TotalOrders'}, inplace=True)
    def cohort_period(df):
        df['CohortPeriod'] = np.arange(len(df)) + 1
        return df
    cohorts = cohorts.groupby(level=0).apply(cohort_period)
    cohorts.reset_index(inplace=True)
    cohorts.set_index(['CohortGroup', 'CohortPeriod'], inplace=True)
    cohort_group_size = cohorts['TotalUsers'].groupby(level=0).first()
    user_retention = cohorts['TotalUsers'].unstack(0).divide(cohort_group_size, axis=1)

    ########################
    ##      Heat Map      ##
    ########################

    # st.write("""
    # ## Heat Map overview
    # """)
    # st.write("""
    # ## Heat Map Cu
    # """)
    
    sns.set(style='white')
    fig3 = plt.figure(figsize=(18, 12))
    sns.heatmap(user_retention.T, mask=user_retention.T.isnull(), annot=True, fmt='.0%')
    col1.pyplot(fig3,use_column_width=True)
    
    heat_map_values = cohorts['TotalUsers'].unstack(0)
    fig4 = plt.figure(figsize=(18, 12))
    sns.heatmap(heat_map_values.T, mask=heat_map_values.T.isnull(), annot=True, fmt='.20g')
    col2.pyplot(fig4,use_column_width=True)
    
    # st.dataframe(heat_map_values.T)

    ########################
    ## Corhort Line Graph ##
    ########################

    col1.write("""
    ## View line graph for individual cohorts
    """)
    selection = col1.selectbox('Choose '+region+' Corhorts',user_retention.columns)
    col1.line_chart(user_retention[selection])

    ########################
    ##   Retention Data   ##
    ########################

    unstacked = cohorts['TotalUsers'].unstack(0)
    unstacked.reset_index()
    weighted = unstacked.reset_index()
    weighted['Total_Subs'] = weighted.drop('CohortPeriod', axis=1).sum(axis=1)
    weighted['num_months'] = weighted['CohortPeriod'].count() - weighted.isnull().sum(axis=1)
    def calc_sum(col_end):
        ans = 0 
        for i in range(1,int(col_end)):
            ans = ans + weighted.iloc[0, i]
        return ans
    def calc_ret_pct(total_subs, num_months):
        sum_initial = calc_sum(1 + num_months)
        
        return total_subs / sum_initial
    weighted['Ret_Pct'] = weighted.apply(lambda row: calc_ret_pct(row['Total_Subs'], row['num_months']), axis=1)
    weighted_avg = weighted.filter(items=['CohortPeriod', 'Ret_Pct'])
    weighted_avg['Ret_Pct'] = pd.Series(["{0:.2f}%".format(val * 100) for val in weighted_avg['Ret_Pct']], index = weighted_avg.index)
    weighted_avg['CohortPeriod'] = weighted_avg['CohortPeriod'].astype(int)
    weighted['Retention Percentage'] = (100 * weighted['Ret_Pct'].round(3))


    ########################
    ##  Cumulative Curve  ##
    ########################

    col2.write("""
    ## Cumulative Retention Curve (excluding period 1)
    """)
   
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x = weighted_avg.iloc[1:]['CohortPeriod'],
        y = weighted_avg.iloc[1:]['Ret_Pct'].str.rstrip('%').astype('float')/100,
    ))
    fig.update_layout(
        yaxis=dict(
            tickformat="%",
            categoryorder="category ascending",
        ),
        xaxis_title="Cohort Period",
        yaxis_title="Retention Percentage",
        font=dict(
            size=18,
        )
    )
    col2.plotly_chart(fig)
    
     #############
    # DL LINK ###
    #############
    
    download=st.button('Download '+region+' cumulative Excel File')
    if download:
        'Download Started! Please wait a link will appear below for your to download the file'
        csv = weighted_avg.to_csv(index=False)
        b64 = base64.b64encode(csv.encode()).decode()  # some strings
        linko= f'<a href="data:file/csv;base64,{b64}" download="myfilename.csv">Download csv file</a>'
        st.markdown(linko, unsafe_allow_html=True)
    
    ########################
    ##  Export            ##
    ########################
    
    # Create a Pandas Excel writer using XlsxWriter as the engine.
    writer = pd.ExcelWriter('Exported File.xlsx', engine='xlsxwriter')

    # Write each dataframe to a different worksheet.
    weighted_avg.to_excel(writer,sheet_name='Cumulative')
    user_retention.to_excel(writer,sheet_name='Cohort')
    heat_map_values.T.to_excel(writer,sheet_name="Cohort Values")

    # Close the Pandas Excel writer and output the Excel file.
    writer.save()

show_cohort_analysis(df,title)