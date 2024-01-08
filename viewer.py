import glob
from datetime import datetime
from pydantic import BaseModel
from helper import Job
import json
from typing import List, Dict
import plotly.graph_objects as go
import plotly.colors as plotly_colors

class Result(BaseModel):
    date: datetime
    node_uuid: str
    job_uuid: str
    run_uuid: str
    job: Job
    
def get_job(filename):
    with open(filename, "r") as result_file:
        job_dict = json.loads(result_file.read())
        job = Job(**job_dict)
    return job

def safe_cast(val, to_type, default=None):
    try:
        return to_type(val)
    except (ValueError, TypeError):
        return default

result_files = glob.glob("result-*.json")
results = [Result(date=datetime.strptime(result_file[7:7+12], '%y%m%d%H%M%S'), node_uuid=result_file[25:25+36], job_uuid=result_file[66:66+36], run_uuid=result_file[107:107+36], job=get_job(result_file)) for result_file in result_files if len(result_file) == 148]
result_groups: List[List[Result]] = []
for result in results:
    result_group = [result]
    results.remove(result)
    for result_2 in results:
        if result.run_uuid == result_2.run_uuid:
            result_group.append(result_2)
            results.remove(result_2)
    result_groups.append(result_group)

i = 0
for result_group in result_groups:
    print(f"{i}: result group with run uuid {result_group[0].run_uuid} from {result_group[0].date.strftime('%y-%m-%d')}")
    i = i + 1
    
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


averages: List[Dict[str, float]] | None = selected_result_group[0].job.averages
values: List[float] = []
average = 0
if averages is not None:
    for data in averages:
        value = data.get("value")
        assert isinstance(value, float)
        values.append(value)
        
    average = sum(values)/len(values)

print("Average Power consumption:", average)


fig = go.Figure()
fig.update_layout(legend_title_text="Jobs", title=selected_result_group[0].run_uuid)
fig.update_xaxes(title_text="Time [ms]")
fig.update_yaxes(title_text="Power [uA]")
i = 0
for result in selected_result_group:
    if result.job.averages is not None and result.job.data_samples is not None:
        fig.add_trace(go.Scatter(x=[x.get("time") for x in result.job.averages], y=[x.get("value") for x in result.job.averages], line=dict(color=plotly_colors.qualitative.Plotly[i]), mode="lines", name=f"{i}: {result.job.uuid}"))
        for data in result.job.data_samples:
            fig.add_vline(
                x=data.get("time"), line_width=3, line_dash="dash", 
                line_color=plotly_colors.qualitative.Plotly[i],
                annotation=dict(
                    text=f"{i}: {data.get('value')}",
                    textangle=-90)
                )
        i += 1
fig.show()