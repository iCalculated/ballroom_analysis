# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/02_scraping.ipynb.

# %% auto 0
__all__ = ['event_names', 'headers', 'soup', 'events', 'Style', 'Event', 'parse_event_name', 'get', 'get_event_list_html',
           'extract_events_from_html', 'Result', 'extract_max_callbacks', 'extract_placement', 'extract_num_dances',
           'get_event_result']

# %% ../nbs/02_scraping.ipynb 3
import requests
from bs4 import BeautifulSoup
from typing import List, Tuple, NamedTuple

# %% ../nbs/02_scraping.ipynb 4
from enum import Enum

class Style(Enum):
    LATIN = 'Latin'
    STANDARD = 'Standard'
    SMOOTH = 'Smooth'
    RHYTHM = 'Rhythm'



class Event(NamedTuple):
    division: str
    level: str
    event: str
    number: int
    style: Style | None = None

    def __str__(self):
        return f"{self.division} {self.level} {self.event}"

def parse_event_name(event_name):
    words = event_name.split()
    number = int(words[0][:-1])
    division = ' '.join(words[1:3])
    level = ' '.join(words[3:5]) if words[4].isdigit() else words[3]
    event = ' '.join(words[5:]) if words[4].isdigit() else ' '.join(words[4:])
    return Event(number=number, division=division, level=level, event=event)

event_names = ['9) Amateur Collegiate Gold Standard', '19) Amateur Collegiate Silver Rhythm', '4) Amateur Collegiate Gold Rhythm', '10) Amateur Adult Silver Rhythm', '2) Amateur Collegiate Silver Standard', '3) Amateur Collegiate Silver Intl. Tango', '4) Amateur Collegiate All Syllabus Standard', '10) Amateur Adult Silver Intl. V. Waltz', '3) Amateur Adult Silver Standard', '3) Amateur Adult Silver Intl. Tango', '11) Amateur Collegiate Silver Smooth', '2) Amateur Adult Gold Smooth', '1) Amateur Collegiate Gold Smooth', '6) Amateur Adult Novice Smooth', '23) Amateur Adult Silver Latin', '9) Amateur Collegiate Silver Latin', '8) Amateur Collegiate Bronze Latin', '15) Amateur Adult Bronze 1 Latin', '8) Amateur Adult Bronze Latin']
for name in event_names:
    print(parse_event_name(name))

# %% ../nbs/02_scraping.ipynb 5
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
}

def get(url, **kwargs):
    return requests.get(url, headers=headers, **kwargs)

def get_event_list_html(name: str) -> BeautifulSoup:
    first, last = name.split(" ", 1)
    url = f"https://results.o2cm.com/individual.asp?szLast={last}&szFirst={first}"
    page: requests.Response = get(url)
    soup = BeautifulSoup(page.content, "html.parser")
    return soup

soup = get_event_list_html("Sasha Hydrie")

# %% ../nbs/02_scraping.ipynb 6
def extract_events_from_html(soup: BeautifulSoup) -> List[Tuple[str, str]]:
    events = []
    include_events = False

    for tag in soup.find_all(['b', 'a']):  
        if tag.name == 'b' and tag.text == '03-22-24 - USA DANCE National DanceSport Championships':
            include_events = True
        elif tag.name == 'b' and include_events:
            break 
        elif tag.name == 'a' and include_events:
            events.append((parse_event_name(tag.text), tag.get('href')))

    return events

events = extract_events_from_html(soup)
events

# %% ../nbs/02_scraping.ipynb 7
class Result(NamedTuple):
    callbacks: int
    placement: float | None
    num_dances: int = 1

# %% ../nbs/02_scraping.ipynb 8
def extract_max_callbacks(soup: BeautifulSoup) -> int:
    select_element = soup.find('select', {'id': 'selCount'})
    possible_callbacks = len(select_element.find_all('option')) - 1 if select_element else 0
    return possible_callbacks

def extract_placement(soup: BeautifulSoup, name: str, verbose=False) -> float | None: 
    """assumes that soup is a finals page"""
    couple_number = None
    for link in soup.find_all('a'):
        if link.text == name:
            parent_td = link.find_parent('td')  # Parent <td> which should have sibling with couple number
            if parent_td:
                # The immediate previous sibling <td> of `parent_td` contains the couple number
                prev_td = parent_td.find_previous_sibling("td", class_="t1b")
                if prev_td:
                    couple_number = prev_td.text.strip()
                    if verbose:
                        print(f"Found {couple_number} associated with {name}")
                    break
    else:
        if verbose:
            print(f"Dancer {name} didn't final")
        return None

    summary_table = soup.find('td', string='Summary').find_parent('table') if soup.find('td', string='Summary') else None
    if summary_table:
        for row in summary_table.find_all('tr'):
            cells = row.find_all('td') 
            if cells and cells[0].get_text(strip=True) == couple_number:
                averaged_place = cells[-1].get_text(strip=True)  
                return float(averaged_place)

    results_table = soup.find('table', class_='t1n')
    for row in results_table.find_all('tr'):
        cells = row.find_all('td') 
        if cells and cells[0].get_text(strip=True) == couple_number:
            averaged_place = cells[-2].get_text(strip=True)  
            return float(averaged_place)

def extract_num_dances(soup: BeautifulSoup) -> int:
    return max(len(soup.find_all('table', class_='t1n')) - 2, 1)


# %% ../nbs/02_scraping.ipynb 10
def get_event_result(name: str, url: str) -> Result:
    query_string = url.split("?")[1]
    key_value_pairs = [query.split("=") for query in query_string.split("&")]
    data: dict[str, str | int] = {key: value for key, value in key_value_pairs}

    # CR shy: factor session creation out
    session = requests.Session()
    session.headers.update(headers)

    initial_res = session.get(url)
    soup = BeautifulSoup(initial_res.content, "html.parser")

    possible_callbacks = extract_max_callbacks(soup)
    num_dances = extract_num_dances(soup)

    if (place := extract_placement(soup, name)) is not None:
        return Result(callbacks=possible_callbacks, placement=place, num_dances=num_dances)


    base_url = "https://results.o2cm.com/scoresheet3.asp"
    # CR shy: binary search eventually
    for selector in range(1, possible_callbacks + 1):
        data["selCount"] = selector
        response = session.post(base_url, data=data)

        # Process the response
        soup = BeautifulSoup(response.content, 'html.parser')

        if name in soup.get_text():
            return Result(callbacks=possible_callbacks - selector, placement=None, num_dances=num_dances)
    else:
        raise ValueError(f"Couldn't find {name} in {url}")

get_event_result("Khalid Ali", "https://results.o2cm.com/scoresheet3.asp?event=usa24&heatid=40423019")
    

