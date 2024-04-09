import glob
from datetime import datetime
from pydantic import BaseModel
from helper import Job
import helper
import json
from typing import List, Dict
import plotly.graph_objects as go
import plotly.colors as plotly_colors
import os
import csv
from uuid import uuid4

SHOW_EVENTS_IN_PLOT = False # if true shows information about every logged event in the web viewer
SHOW_POWER_IN_PLOT = True # if true shows information about the power usage and time of each complete cycle in the web viewer
SHOW_RECEIVER_IN_PLOT = False # if true shows the graph for a receiver in the web viewer if it is covered in the filters below

SHIFT_SENDER_TIME_TO_FIRST_ADC = True # if true shifts all time values to the first ADC Read event marked by ADC_READ
SHIFT_SENDER_TIME_TO_FIRST_VALUE = False# if true sets the first time value of all selected results to the 0 mark

CYCLE_KEY_WORD = "READY" # keyword for the cycle detection
OPTION_FILTERS = ["WIFI", "DEEP_SLEEP", "EXAMPLE_POWER_SAVE_MIN_MODEM"] # protocol, sleep and power save mode filters for the available results, does not work for receiver in plot

class Result(BaseModel):
    date: datetime
    node_uuid: str
    job_uuid: str
    run_uuid: str
    job: Job
    
def get_first_adc_time(data_samples):
    return [data_sample for data_sample in data_samples if data_sample.get("value") == "ADC_READ"][0]["time"]
    
# load all available result files in the specified directory and parse them
def get_job(foldername):
    result_files = glob.glob(f"{os.path.join(helper.BASE_DIR, foldername)}/*.json")
    first_file = result_files[0]
    result_files.remove(first_file)
    with open(first_file, "r") as first_file_open:
        summed_job = Job(**json.loads(first_file_open.read()))
        for file in result_files:
            with open(file, "r") as file_open:
                job_dict = json.loads(file_open.read())
                job = Job(**job_dict)
                if summed_job.averages and job.averages:
                    summed_job.averages.extend(job.averages)
                if summed_job.data_samples and job.data_samples:
                    summed_job.data_samples.extend(job.data_samples)
                elif not summed_job.data_samples and job.data_samples:
                    summed_job.data_samples = job.data_samples
        
        if summed_job.averages:
            summed_job.averages = sorted(summed_job.averages, key=lambda val:val["time"])
        if summed_job.data_samples:
            summed_job.data_samples = sorted(summed_job.data_samples, key=lambda val:val["time"])
        if SHIFT_SENDER_TIME_TO_FIRST_ADC and summed_job.type == "sender":
            first_adc_time = get_first_adc_time(summed_job.data_samples)
            if summed_job.averages:
                for average in summed_job.averages:
                    average["time"] = average["time"] - first_adc_time
            if summed_job.data_samples:
                for data_sample in summed_job.data_samples:
                    data_sample["time"] = data_sample["time"] - first_adc_time
        elif SHIFT_SENDER_TIME_TO_FIRST_VALUE and summed_job.type == "sender":
            if summed_job.averages:
                first_adc_time = summed_job.averages[0]["time"]
                for average in summed_job.averages:
                    average["time"] = average["time"] - first_adc_time
                if summed_job.data_samples:
                    for data_sample in summed_job.data_samples:
                        data_sample["time"] = data_sample["time"] - first_adc_time
            
    return summed_job

def safe_cast(val, to_type, default=None):
    try:
        return to_type(val)
    except (ValueError, TypeError):
        return default

# find all result files with the correct name format
result_folders = glob.glob("result-*")
results = [Result(date=datetime.strptime(result_folder[7:7+12], '%y%m%d%H%M%S'), node_uuid=result_folder[25:25+36], job_uuid=result_folder[66:66+36], run_uuid=result_folder[107:107+36], job=get_job(result_folder)) for result_folder in result_folders if len(result_folder) >= 100]
result_groups: List[List[Result]] = []
for result in results:
    result_group = [result]
    for result_2 in [res for res in results if res != result and result.run_uuid not in [res_g[0].run_uuid for res_g in result_groups]]:
        if result.run_uuid == result_2.run_uuid:
            result_group.append(result_2)
    if result_group[0].run_uuid not in [res_g[0].run_uuid for res_g in result_groups]:
        result_groups.append(result_group)

i = 0
for result_group in result_groups:
    print(f"{i}: result group with run uuid {result_group[0].run_uuid} from {datetime.utcfromtimestamp(result_group[0].job.started_at).strftime('%y-%m-%d %H:%M:%S')}")
    i = i + 1
    
# select a single result group for viewing
selected_result_group: List[Result] = []
while selected_result_group == []:
    input_selected = input("Select run data by entering number: ")
    try:
        if int(input_selected) >= len(result_groups) or int(input_selected) < 0:
            print("Not a valid input!")
            selected_result_group = []
        number = int(input_selected)
        selected_result_group = result_groups[number]
    except:
        print("Could not parse input!")
print("Selected group with run uuid", selected_result_group[0].run_uuid)

def get_sender_index(result_group: List[Result]):
    for i in range(0, len(result_group)):
        if result_group[i].job.type == "sender":
            return i
    return None
    
# calculate average power of result with specified index
def calculate_average(index):
    averages: List[Dict[str, float]] | None = selected_result_group[index].job.averages
    values: List[float] = []
    average = 0
    total_time = 0
    if averages is not None:
        for data in averages:
            value = data.get("value")
            assert isinstance(value, float)
            values.append(value)
            
        average = sum(values)/len(values)
        first_timestamp = averages[0].get("time") # ms
        last_timestamp = averages[len(averages)-1].get("time") # ms
        if first_timestamp is not None and last_timestamp is not None:
            total_time = (last_timestamp - first_timestamp) / 1000 # s

    print("Average Power consumption:", average / 1000, "mA over", total_time, "seconds")
    return average, total_time

def get_float_range(dict, start, end):
    return {key:dict[key] for key in dict.keys() if key >= start and key <= end}

def get_word_entries(dict, keyword):
    return {key:dict[key] for key in dict.keys() if dict[key] == keyword}

# get all information about the available results and their complete cycles marked by the set CYCLE_KEY_WORD
def get_total_power_cycle():
    all_cycle_powers : List[List[tuple[float, float, float]]] = []
    csv_uuid = uuid4()
    for i in range(len(selected_result_group)):
        if selected_result_group[i].job.type == "sender":
            index = i
            print(f"Options: {selected_result_group[i].job.protocol}, {selected_result_group[i].job.sleep_mode}, {selected_result_group[i].job.power_save_mode}")        
            averages: List[Dict[str, float]] | None = selected_result_group[i].job.averages
            data_samples: List[Dict[str, str]] | None = selected_result_group[i].job.data_samples
            values: Dict[float, float] = {}
            events: Dict[float, str] = {}
            if averages is not None and data_samples is not None:
                for average in averages:
                    if (time := average.get("time")) and (value := average.get("value")):
                        values[time] = value        
                for data in data_samples:
                    if (time := data.get("time")) and (value := data.get("value")):
                        events[float(time)] = value
                        
            adc_reads = list(get_word_entries(events, CYCLE_KEY_WORD).keys())
            total_power_mAh = 0
            total_time = 0
            cycle_powers: List[tuple[float, float, float]] = []
            for i in range(0, len(adc_reads)-1):
                cycle_power_mAh = 0
                first_timestamp = adc_reads[i] # ms
                second_timestamp = adc_reads[i + 1] # ms
                overall_time_diff = (second_timestamp - first_timestamp) / 1000 # s
                power_values_in_range = list(get_float_range(values, first_timestamp, second_timestamp).items())
                for j in range(0, len(power_values_in_range)-1):
                    first_power_timestamp = power_values_in_range[j][0] # ms
                    second_power_timestamp = power_values_in_range[j + 1][0] # ms
                    first_power_value = power_values_in_range[j][1] # uA
                    second_power_value = power_values_in_range[j + 1][1] # uA
                    power_time_diff = (second_power_timestamp - first_power_timestamp) / 1000 # s
                    power_value_avg = (second_power_value + first_power_value) / 2 # uA
                    corrected_power_value_diff = (power_value_avg / 1000) * (power_time_diff / 3600) # mAh
                    # print("Time-Diff:", power_time_diff, "Power-Diff:", power_value_avg, "Corrected-Power-Diff:", corrected_power_value_diff)
                    cycle_power_mAh = cycle_power_mAh + corrected_power_value_diff # mAh
                cycle_power_mWh = cycle_power_mAh * 3.3 # mWh
                cycle_powers.append((cycle_power_mAh, cycle_power_mWh, overall_time_diff))
                print(f"Cycle {i+1}:", cycle_power_mAh, "mAh |", cycle_power_mWh, "mWh | Average Power:", (cycle_power_mWh/(overall_time_diff/3600)), "mW / ", (cycle_power_mAh/(overall_time_diff/3600)), "mA over", overall_time_diff, "seconds")
                total_power_mAh = total_power_mAh + cycle_power_mAh # mAh
                total_time = total_time + overall_time_diff # s
            total_power_mWh = total_power_mAh * 3.3
            print("Total:", total_power_mAh, "mAh |", total_power_mWh, "mWh in", len(adc_reads) - 1, "full cycles")
            all_cycle_powers.append(cycle_powers)
            file_exists = os.path.isfile(f'{csv_uuid}.csv')
            row = [selected_result_group[index].job.protocol, selected_result_group[index].job.sleep_mode, selected_result_group[index].job.power_save_mode, total_power_mWh, len(adc_reads) - 1 ,total_time]
            with open(f'{csv_uuid}.csv', 'a', newline='') as file:
                writer = csv.writer(file)
                if not file_exists:
                    field = ["PROTOCOL", "SLEEP_MODE", "POWER_SAVE_MODE", "TOTAL_POWER", "CYCLE_COUNT", "TOTAL_TIME"]
                    writer.writerow(field)
                    
                writer.writerow(row)
    return all_cycle_powers

# show all selected plots in a interactive web viewer
def show_plot(all_powers: List[List[tuple[float, float, float]]]):
    fig = go.Figure()
    fig.update_layout(legend_title_text="Jobs", title=selected_result_group[0].run_uuid)
    fig.update_xaxes(title_text="Time [ms]")
    fig.update_yaxes(title_text="Power [uA]")
    i = 0
    j = 0
    for result in [node for node in selected_result_group if node.job.type == "sender" or SHOW_RECEIVER_IN_PLOT]:
        if not OPTION_FILTERS or (result.job.protocol in OPTION_FILTERS and result.job.sleep_mode in OPTION_FILTERS and result.job.power_save_mode in OPTION_FILTERS):
            power_index = 0
            j = [node for node in selected_result_group if node.job.type == "sender" or SHOW_RECEIVER_IN_PLOT].index(result)
            if result.job.averages is not None and result.job.data_samples is not None:
                fig.add_trace(go.Scatter(x=[x.get("time") for x in result.job.averages], y=[x.get("value") for x in result.job.averages], line=dict(color=plotly_colors.qualitative.Plotly[i]), mode="lines", name=f"{result.job.protocol}, {result.job.sleep_mode}, {result.job.power_save_mode}"))
                for data in result.job.data_samples:
                    if SHOW_EVENTS_IN_PLOT:
                        fig.add_vline(
                            x=data.get("time"), line_width=3, line_dash="dash", 
                            line_color=plotly_colors.qualitative.Plotly[i],
                            annotation=dict(
                                text=f"{i}: {data.get('value')}",
                                textangle=-90)
                            )
                    if SHOW_POWER_IN_PLOT:
                        print(j)
                        if all_powers[j] is not None and data.get("value") == "ADC_READ":
                            if power_index < len(all_powers[j]):
                                mAh, mWh, time = all_powers[j][power_index]
                                if (timestamp := data.get("time")) is not None:
                                    fig.add_annotation(x=timestamp + time * 500, y=5 + 10000 * i,
                                        text=f"<b>Options: {result.job.protocol}, {result.job.sleep_mode}, {result.job.power_save_mode}</b><br><b>Cycle {power_index + 1}</b><br>{mWh} mWh<br>in {time} seconds",
                                        font=dict(color=plotly_colors.qualitative.Plotly[i]),
                                        xref='x', yref='y')
                                    power_index = power_index + 1
                i += 1
                # if result.job.type == "sender":
                # j += 1
                if i > 9:
                    i = 0
    fig.show()
    
show_plot(get_total_power_cycle())