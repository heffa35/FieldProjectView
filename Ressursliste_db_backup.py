#!/usr/bin/env python
# coding: utf-8

import pandas as pd
import numpy as np
import sqlite3
import streamlit as st
import datetime
import altair as alt
import plotly.express as px
from isort.sorting import sort
from pandas._libs.tslibs.offsets import BDay
from st_aggrid import AgGrid, GridUpdateMode, JsCode
from st_aggrid.grid_options_builder import GridOptionsBuilder
from pandas.tseries.offsets import CustomBusinessDay



st.set_page_config(layout="wide")
Efficiant_Hours_Per_Day = 4.5

def load_data():
    df = pd.read_csv("./prosjektoversikt.csv", parse_dates=['PDD'],
                     date_parser=lambda d: pd.to_datetime(d, format='%Y-%m-%d'))
    return df


def createConnection(db_file):
    conn = None
    try:
        conn = sqlite3.connect(db_file)
    except Error as e:
        print(e)
    return conn


def getFullName(LoginName):
    conn = createConnection("./data.db")
    cur = conn.cursor()
    cur.execute("SELECT Last_Name, First_Name from tbl_Resources where Login_Name =?", (LoginName,))
    n = cur.fetchall()
    result = n[0][0] + ", " + n[0][1]
    return result

def getResources():
    conn = createConnection("./data.db")
    cur = conn.cursor()
    
    cur.execute("SELECT Last_Name, First_Name, Producer from tbl_Resources WHERE Producer = 'TRUE' ORDER BY Last_Name")
    n = cur.fetchall()
    result = []
    for i in range(0, len(n)):
        r = n[i][0] + ", " + n[i][1]
        result.append(r)
    return result

def getResource_ID(LastName, FirstName):
    conn = createConnection("./data.db")
    cur = conn.cursor()
    cur.execute("SELECT Resource_ID from tbl_Resources where Last_Name =? AND First_Name=?", (LastName,FirstName,))
    n = cur.fetchall()
    if (len(n)>0):
        result = n[0][0]
    else:
        result = -1
    return result


#name = getFullName("sangolts")
#print(name)
#names = getResources()
#print(names)
#resource_id = getResource_ID('Sangolt','Sindre')
#print(resource_id)

#st.write(name)
#

def getResourcesHours(resource_id,show_option):
    conn = createConnection("./data.db")
    cur = conn.cursor()
    cur.execute("SELECT tbl_Projects.Tracker_No, tbl_Projects.Rigname, tbl_Projects.SO_Description, tbl_Resources_Hours.Planned_Hours, tbl_Projects.KO_Promised_Date, tbl_Resources_Hours.Progress_Percentage, tbl_Projects.Holiday, tbl_Projects.Fixed_Dates from tbl_Resources_Hours INNER JOIN tbl_Projects ON tbl_Resources_Hours.Tracker_No=tbl_Projects.Tracker_No WHERE tbl_Resources_Hours.Resource_ID=? AND Progress_Percentage {} 100 ORDER BY tbl_Projects.KO_Promised_Date DESC".format(show_option), (resource_id,))
    n = cur.fetchall()
    if (len(n) < 1):
        return None
    else:      
        return n

@st.cache(allow_output_mutation=True)
def GetProjectHours(resource_id, show_option):
    result = getResourcesHours(resource_id, show_option)
    if result is None:
        return None
    project_hours = pd.DataFrame.from_records(result, columns=['Tracker_No','Rigname','SO_Description','Planned_Hours','Promised_Date','Progress_Percentage','Holiday','Fixed_Dates'])
    project_days = []
    for r in result:
        # Calc days of work deducting reported progress
        project_days.append(round((r[3] / Efficiant_Hours_Per_Day) * ((100 - r[5]) / 100)))

    project_hours['Project_Days'] = project_days
    project_hours['Promised_Date'] = project_hours['Promised_Date'].astype('datetime64')
    start_date = []
    expected_delivery_date = []
    project_late_start = []
    holiday_dates = []
    previous_start_date = pd.to_datetime('2099-12-31')
    for i in range(0, len(project_hours.index)):
        p_date = project_hours.at[i, 'Promised_Date']
        p_days = project_hours.at[i, 'Project_Days']
        if (project_hours.at[i,'Fixed_Dates'] == True):
            for j in range(0, p_days):
                holiday_dates.append(p_date.date() - BDay(j))

    for i in range(0, len(project_hours.index)):
        p_date = project_hours.at[i, 'Promised_Date']
        p_days = project_hours.at[i, 'Project_Days']
        if (project_hours.at[i,'Fixed_Dates'] == True):
            s_date = p_date - BDay(p_days)
            expected_delivery_date.append(p_date)
            project_late_start.append(False)
        else:
            if (p_date > previous_start_date):
                p_date = previous_start_date-CustomBusinessDay(n=1, holidays=holiday_dates)
            s_date = p_date - CustomBusinessDay(n=p_days, holidays=holiday_dates)
            if (pd.Timestamp.today() > s_date):
                s_date = pd.Timestamp.today()
                expected_delivery_date.append(pd.Timestamp.today() + CustomBusinessDay(n=p_days, holidays=holiday_dates))
                project_late_start.append(True)
            else:
                expected_delivery_date.append(p_date)
                project_late_start.append(False)
        start_date.append(s_date)
        if (previous_start_date > s_date):
            previous_start_date = s_date

    project_hours['Latest_Start_Date'] = start_date
    project_hours['Expected_Delivery_Date'] = expected_delivery_date
    project_hours['Project_Late_Start'] = project_late_start

    return project_hours


def GetWorkLoad(project_hours):
    workload = pd.DataFrame()
    work_dates = []
    today = datetime.datetime.now()
    days_to_last_project_delivery = np.busday_count(today.date(), project_hours.at[0, 'Promised_Date'].date())
    scheduled_day_hours = []
    overtime_day = []
    day_booked = []
    for i in range(0, days_to_last_project_delivery):
        date = today.date() + BDay(i)
        work_dates.append(date)
        scheduled_day_hours.append(0)
        overtime_day.append(0)
        day_booked.append(0)
        for j in range(0, len(project_hours.index)):
            if (project_hours.at[j, 'Latest_Start_Date'] <= date ) and (project_hours.at[j, 'Expected_Delivery_Date'] > date ):
                scheduled_day_hours[i] = scheduled_day_hours[i] + Efficiant_Hours_Per_Day
                day_booked[i] = 1
                if (scheduled_day_hours[i] > Efficiant_Hours_Per_Day ):
                    overtime_day[i] = 1
                else:
                    overtime_day[i] = 0

    workload['Date'] = work_dates
    workload['Scheduled_Hours'] = scheduled_day_hours
    workload['Overtime_Required'] = overtime_day
    workload['Day_Booked'] = day_booked
    return workload


def row_selected(self, msg):
    print(msg)
    if msg.selected:
        print(msg.data)
        print(msg.rowIndex)
    elif self.row_selected == msg.rowIndex:
        print('self.row_selected == msg.rowIndex')

def writeData(df):
    tr = []
    rg = []
    so = []
    pr = []
    conn = createConnection("./data.db")
    cur = conn.cursor()
    for i in range(0, len(df.index)):
        Tracker_NO = df.iat[i,0]
        Rigname = df.iat[i,1].split(' - ')[0]
        Rigname = Rigname.rstrip()
        SO_Description = df.iat[i,1].split(' - ')[1]
        SO_Description = SO_Description.lstrip()
        KO_Promised_Date = df.iat[i,2]
        ln = df.iat[i,3].split(',', 1)[0]
        fn = df.iat[i,3].split(',', 1)[1].lstrip()
        resource_id = getResource_ID(ln, fn)
        if resource_id != -1:
            Planned_Hours = int(df.iat[i,4])
            if not Tracker_NO in tr:
                tr.append(Tracker_NO)
                rg.append(Rigname)
                so.append(SO_Description)
                pr.append(KO_Promised_Date)
            sql = "INSERT INTO  tbl_Resources_Hours (Tracker_NO, Resource_ID, Planned_Hours, Progress_Percentage) VALUES (?, ?, ?,?)"
            values = (Tracker_NO, resource_id, Planned_Hours,0)
            cur.execute(sql, values)
            conn.commit()
    for i in range(0, len(tr)):
        if pr[i]>pd.Timestamp('2022-04-01 00:00:00'):
            sql ="INSERT INTO  tbl_Projects (Tracker_NO, Rigname, SO_Description, KO_Promised_Date) VALUES (?, ?, ?, ?)"
            values = (tr[i], rg[i], so[i], str(pr[i]))
            cur.execute(sql, values)
            conn.commit()

#--------------------------------------------------------
#temp_df=load_data()
#st.write(temp_df)
#writeData(temp_df)
#--------------------------------------------------------



def updatepercentage(percentage,trackerno,resource_id):
    conn = createConnection("./data.db")
    cur = conn.cursor()
    sql="UPDATE tbl_Resources_Hours SET Progress_Percentage = {} WHERE Tracker_No = '{}' AND Resource_ID = {}".format(percentage,trackerno,resource_id)
    
    cur.execute(sql)
    
    conn.commit()
    conn.close()


def displayGrid(ph):
    ph = ph.iloc[::-1]

    gb = GridOptionsBuilder.from_dataframe(ph)

    gb.configure_default_column(editable=True)
    gb.configure_selection(selection_mode='single', use_checkbox=False)
    gb.configure_column("Progress_Percentage", editable=True, cellEditor='agSelectCellEditor',
                        cellEditorParams={'values': [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]})
    gb.configure_columns(['Holiday','Fixed_Dates','Project_Days','Project_Late_Start'], hide=True)
    gridoptions = gb.build()
    grid_response = AgGrid(
        ph,
        editable=True,
        gridOptions=gridoptions,
        width='100%',
        theme="streamlit",
        fit_columns_on_load=True
    )
    if (grid_response['selected_rows']):
        ph_test = grid_response['data']
        selected_rows_df = pd.DataFrame(grid_response['selected_rows'])
        tracker_no = selected_rows_df.at[0, 'Tracker_No']
        percentage = selected_rows_df.at[0, 'Progress_Percentage']
        # st.write(tracker_no)
        # st.write(selected_rows_df.iat[0,5])
        # st.write(selected_rows_df.iat[0,0])
        # st.write(resource_id)

        updatepercentage(percentage, tracker_no, resource_id)
        st.legacy_caching.clear_cache()
        st.experimental_rerun()


def displayChart(wl):
    chart = (
        alt.Chart(wl)
        .mark_bar()
        .encode(
            alt.X("Date"),
            alt.Y("Day_Booked"),
            alt.Color("Overtime_Required", scale=alt.Scale(domain=[0,1], range=['green','red']), legend=None),
        )
        .properties(
            width=1400,
            height=150,
        )
        .interactive()
    )
    st.altair_chart(chart)

def displayGantChart(ph):
    #ph = ph.iloc[::-1]    
    ph['Fixed_Dates'].replace(1,'red')
    ph['Fixed_Dates'].replace(0,'orange')
    fig = px.timeline(
        ph,
        x_start="Latest_Start_Date",
        x_end="Expected_Delivery_Date",
        y="Tracker_No",
        color_discrete_map={False:'blue',True:'orange'},
        color="Fixed_Dates",
	color_continuous_scale=[[0, 'blue'], [1, 'red']],
        hover_name="SO_Description"
    )
    fig.update(layout_coloraxis_showscale=False)
    fig.update_layout(
        hoverlabel_bgcolor='#DAEEED',
        # Change the hover tooltip background color to a universal light blue color. If not specified, the background color will vary by team or completion pct, depending on what view the user chooses
        bargap=0.2,
        height=600,
        xaxis_title="",
        yaxis_title="",
        title_x=0.5,  # Make title centered
        xaxis=dict(
            tickfont_size=15,
            tickangle=270,
            rangeslider_visible=True,
            side="top",  # Place the tick labels on the top of the chart
            showgrid=True,
            zeroline=True,
            showline=True,
            showticklabels=True,
            tickformat="%x\n",

        )
    )
    fig.update_xaxes(tickangle=0, tickfont=dict(family='Rockwell', color='blue', size=15))
    st.plotly_chart(fig, use_container_width=True)  # Display the plotly chart in Streamlit


names = getResources()
user = st.sidebar.selectbox("Select Employee",names)
option = st.sidebar.radio(
     'What projects to show',
     ('All', 'Not Completed', 'Completed'))
if option == 'Not Completed':
    show_option = '<'
elif option == 'Completed':
    show_option = '='
else:
    show_option = '<='

ln = user.split(',',1)[0]
fn = user.split(',',1)[1].lstrip(" ")
resource_id = int(getResource_ID(ln,fn))
st.title("Field Engineering SVG Projectview")
ph = (GetProjectHours(resource_id,show_option))
if (ph is not None):
    wl = GetWorkLoad(ph)
    displayGrid(ph)
   #     displayChart(wl)
    displayGantChart(ph)
else:
    st.write("No projects assigned.")
