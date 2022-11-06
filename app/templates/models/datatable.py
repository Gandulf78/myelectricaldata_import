from datetime import datetime
from dependencies import daterange


class Datatable:

    def __init__(self, usage_point_id):
        self.usage_point_id = usage_point_id

    def html(self, title, tag, daily_data, cache_last_date):
        result = f"""
        <table id="dataTable{title}" class="display">
            <thead>
                <tr>
                    <th class="title">Date</th>
                    <th class="title">{title} (W)</th>
                    <th class="title">{title} (kW)</th>
                    <th class="title">Échec</th>
                    <th class="title">En&nbsp;cache</th>
                    <th class="title">Cache</th>
                    <th class="title">Liste noire</th>
                </tr>
            </thead>
            <tbody>
        """
        all_data = {}
        recap = {}
        if daily_data:
            for data in daily_data:
                date_str = data.date.strftime("%Y-%m-%d")
                all_data[date_str] = {
                    "value": data.value,
                    "blacklist": data.blacklist,
                    "fail_count": data.fail_count,
                }
            start_date = cache_last_date
            end_date = datetime.now()
            if start_date:
                for single_date in daterange(start_date, end_date):
                    year = single_date.strftime("%Y")
                    month = single_date.strftime("%m")
                    if year not in recap:
                        recap[year] = {
                            "value": 0,
                            "month": {"01": 0, "02": 0, "03": 0, "04": 0, "05": 0, "06": 0, "07": 0,
                                      "08": 0, "09": 0,
                                      "10": 0, "11": 0,
                                      "12": 0,
                                      }
                        }
                    date_text = single_date.strftime("%Y-%m-%d")
                    conso_w = "0"
                    conso_kw = "0"
                    cache_state = f'<div id="{tag}_icon_{date_text}" class="icon_failed">0</div>'
                    reset = f"""
                    <div id="{tag}_import_{date_text}" name="import_{self.usage_point_id}_{date_text}" class="datatable_button datatable_button_import">
                        <input type="button" value="Importer"></div>
                    <div id="{tag}_reset_{date_text}" name="reset_{self.usage_point_id}_{date_text}"  class="datatable_button">
                        <input type="button" value="Vider" style="display: none"></div>
                    """

                    if date_text in all_data:
                        fail_count = all_data[date_text]["fail_count"]
                        if fail_count == 0:
                            value = all_data[date_text]["value"]
                            blacklist_state = all_data[date_text]["blacklist"]
                            recap[year]["value"] = recap[year]["value"] + value
                            recap[year]['month'][month] = recap[year]['month'][month] + value
                            conso_w = f"{value}"
                            conso_kw = f"{value / 1000}"
                            cache_state = f'<div id="{tag}_icon_{date_text}" class="icon_success">1</div>'
                            reset = f"""
                            <div id="{tag}_import_{date_text}" name="import_{self.usage_point_id}_{date_text}" class="datatable_button datatable_button_import" style="display: none">
                                <input type="button" value="Importer"></div>
                            <div id="{tag}_reset_{date_text}"  name="reset_{self.usage_point_id}_{date_text}"  class="datatable_button">
                                <input type="button" value="Vider"></div>
                            """
                            display_blacklist = ''
                            display_whitelist = ''
                            if blacklist_state == 1:
                                display_blacklist = 'style="display: none"'
                            else:
                                display_whitelist = 'style="display: none"'
                            blacklist = f"""
                            <div class="datatable_button datatable_blacklist datatable_button_disable" id="{tag}_blacklist_{date_text}" name="blacklist_{self.usage_point_id}_{date_text}" {display_blacklist}>
                                <input type="button" value="Blacklist"></div>
                            <div class="datatable_button datatable_whitelist" id="{tag}_whitelist_{date_text}" name="whitelist_{self.usage_point_id}_{date_text}" {display_whitelist}>
                                <input type="button"  value="Whitelist"></div>
                            """
                        else:

                            blacklist = f"""
                            <div class="datatable_button datatable_blacklist" id="{tag}_blacklist_{date_text}" name="blacklist_{self.usage_point_id}_{date_text}">
                                <input type="button" value="Blacklist"></div>
                            <div class="datatable_button datatable_whitelist" id="{tag}_whitelist_{date_text}" name="whitelist_{self.usage_point_id}_{date_text}">
                                <input type="button"  value="Whitelist" style="display: none"></div>
                            """
                    else:
                        fail_count = 0
                        blacklist = f"""
                        <div class="datatable_button datatable_blacklist" id="{tag}_blacklist_{date_text}" name="blacklist_{self.usage_point_id}_{date_text}">
                           <input type="button" value="Blacklist"></div>
                       <div class="datatable_button datatable_whitelist" id="{tag}_whitelist_{date_text}" name="whitelist_{self.usage_point_id}_{date_text}">
                           <input type="button" value="Whitelist" style="display: none"></div>
                        """

                    result += f"""
                    <tr>
                        <td><b>{date_text}</b></td>
                        <td id="{tag}_conso_w_{date_text}">{conso_w} W</td>
                        <td id="{tag}_conso_kw_{date_text}">{conso_kw} kW</td>
                        <td id="{tag}_fail_count_{date_text}">{fail_count}</td>
                        <td>{cache_state}</td>
                        <td class="loading_bg">{reset}</td>
                        <td class="loading_bg">{blacklist}</td>
                    </tr>"""
            result += "</tbody></table>"
        return {
            "recap": recap,
            "html": result
        }
