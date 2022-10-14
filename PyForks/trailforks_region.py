import pandas as pd
import requests
import re
from bs4 import BeautifulSoup
from tqdm import tqdm
from concurrent.futures import as_completed, ThreadPoolExecutor
from PyForks.trailforks import Trailforks, authentication

class TrailforksRegion(Trailforks):

    def is_valid_region(self) -> bool:
        """
        Check to make sure a region name is a real region by
        making sure the page title is not Error

        Returns:
            bool: True:is an existing region;False:region does not exist.
        """
        uri = f"https://www.trailforks.com/region/{self.region}"
        r = requests.get(uri)
        non_existant = "<title>Error</title>"
        if non_existant in r.text:
            return False
        return True

    def check_region(self) -> None:
        """
        A wrapper function for is_valid_region() that conducts an
        exit if the region is non-existant.
        """
        if not self.is_valid_region():
            print(f"[!] {self.region} is not a valid Trailforks Region.")
            exit(1)

    @authentication
    def download_all_region_trails(self, region_id: str, output_path=".") -> bool:
        """
        Each region has a CSV export capability to export all trails within the region.
        This function automates that export for the end user and saves a csv to local
        disk.

        Args:
            region_id (str): this is the integer (string representation) of the region
            output_path (str, optional): output directory for the CSV. Defaults to ".".

        Returns:
            bool: True:export successful;False:export failed.
        """
        self.check_region()
        uri = f"https://www.trailforks.com/tools/trailspreadsheet_csv/?cols=trailid,title,aka,activitytype,difficulty,status,condition,region_title,rid,difficulty_system,trailtype,usage,direction,season,unsanctioned,hidden,rating,ridden,total_checkins,total_reports,total_photos,total_videos,faved,views,global_rank,created,land_manager,closed,wet_weather,distance,time,alt_change,alt_max,alt_climb,alt_descent,grade,dst_climb,dst_descent,dst_flat,alias,inventory_exclude,trail_association,sponsors,builders,maintainers&rid={region_id}"
        r = self.trailforks_session.get(uri, allow_redirects=True)
        raw_csv_data = r.text
        clean_data = re.sub(r'[aA-zZ]\n', "\",", raw_csv_data)

        open(f"{output_path}/{self.region}_trail_listing.csv", "w").write(clean_data)

    @authentication
    def download_all_region_ridelogs(self, output_path=".") -> bool:
        """
        Downloads all of the trail ridelogs since the begining of the 
        trails existance and stores the results in CSV format on the 
        local disk

        Args:
            output_path (str, optional): Path to store csv. Defaults to ".".

        Returns:
            bool: True:successfully saved data;False:failed
        """
        self.check_region()
        region_info = self.__get_region_info()
        total_pages = round(region_info["total_ridelogs"]/30)
        dataframes_list = []

        pbar = tqdm(total=total_pages, desc=f"Enumerating {self.region} Rider Pages")
        for i in range(1, total_pages + 1):
            try:
                domain = f"https://www.trailforks.com/region/{self.region}/ridelogs/?viewMode=table&page={i}"
                tmp_df = pd.read_html(domain, index_col=None, header=0)

                # Sometimes we have more than 1 table on the page.
                if len(tmp_df) >= 2:
                    for potential_df in tmp_df:
                        if "city" not in potential_df.columns:
                            good_df = potential_df
                            dataframes_list.append(good_df)
                else:
                    good_df = tmp_df[0]
                    dataframes_list.append(good_df)

                pbar.update(1)
            except Exception as e:
                pbar.update(1)
                break
        pbar.close()

        df = pd.concat(dataframes_list, axis=0, ignore_index=True)
        df.to_csv(f"{output_path}/{self.region}_scraped_riders.csv")
        

    def __get_region_info(self) -> dict:
        """
        Pulls region specific metrics from the region page

        Returns:
            dict: {total_ridelogs, unique_riders, trails_ridden, avg_trails_per_ride}
        """
        region_uri = f'https://www.trailforks.com/region/{self.region}/ridelogstats/'
        page = requests.get(region_uri)
        soup = BeautifulSoup(page.text, 'html.parser')
        data = soup.find_all("div", class_="col-2 center")
        data = str(data[0])
        soup_1 = BeautifulSoup(data, "html.parser")
        list_items = soup_1.find_all("li")

        region_info = {
            "total_ridelogs": None,
            "unique_riders": None,
            "trails_ridden": None,
            "average_trails_per_ride": None
        }
        region_vars = ["total_ridelogs", "unique_riders", "trails_ridden", "average_trails_per_ride"]

        for i, item in enumerate(list_items):
            region_info[region_vars[i]] = int(re.search(r'>([0-9].*)<', str(item)).groups()[0].replace(",",""))
        
        return region_info
