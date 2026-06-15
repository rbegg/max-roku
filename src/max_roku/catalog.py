
NETFLIX_CATALOG = [
    {"Title": "Anne with an E", "ContentID": "80136311", "Type": "episode"},
    {"Title": "Heartland", "ContentID": "70171946", "Type": "episode"},
    {"Title": "Dolly Parton's Heartstrings", "ContentID": "80244846", "Type": "episode"},
    {"Title": "Happiness for Beginners", "ContentID": "81418617", "Type": "movie"},
    {"Title": "Leap Year", "ContentID": "70124331", "Type": "movie"},
]
NETFLIX_APP_ID = "12"

class Catalog:

    def __init__(self, catalog):
        """Initialize the catalog"""
        self.catalog = catalog
        self.current_channel = 0
        self.max_channel = len(NETFLIX_CATALOG) -1

    def current(self) -> tuple[str, str]:
        title = self.catalog[self.current_channel]["Title"]
        print(f"Playing: {title}")
        return self.catalog[self.current_channel]["ContentID"], self.catalog[self.current_channel]["Type"]

    def next(self) -> tuple[str, str]:
        if self.current_channel + 1 < self.max_channel:
            self.current_channel += 1
        else:
            self.current_channel = 0
        title = self.catalog[self.current_channel]["Title"]
        print(f"Playing: {title}")
        return self.catalog[self.current_channel]["ContentID"], self.catalog[self.current_channel]["Type"]

    def prev(self) -> tuple[str, str]:
        if self.current_channel - 1 >= 0:
            self.current_channel -= 1
        else:
            self.current_channel = self.max_channel
        title = self.catalog[self.current_channel]["Title"]
        print(f"Playing: {title}")
        return self.catalog[self.current_channel]["ContentID"], self.catalog[self.current_channel]["Type"]