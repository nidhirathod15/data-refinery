import pandas as pd
import re
from dateutil import parser

class RefineryEngine:
    def __init__(self, file_path):
        self.file_path = file_path
        self.df = None

    def load_data(self):
        """Ultra-tough loader to prevent 'Expected X fields' errors."""
        if self.file_path.endswith('.csv'):
            try:
                # The 'on_bad_lines' skips rows that are broken/messy
                self.df = pd.read_csv(self.file_path, encoding='utf-8', on_bad_lines='skip')
            except UnicodeDecodeError:
                self.df = pd.read_csv(self.file_path, encoding='latin1', on_bad_lines='skip')
        
        elif self.file_path.endswith(('.xlsx', '.xls')):
            self.df = pd.read_excel(self.file_path, engine='openpyxl')
        
        else:
            raise ValueError("File format not supported by the Refinery.")

    def clean_text(self, text):
        """Standardizes names/cities by removing weird symbols."""
        if pd.isna(text): return text
        # Removes things like !! or *** but keeps letters and numbers
        return re.sub(r'[^a-zA-Z0-9\s]', '', str(text)).strip()

    def parse_numbers(self, value):
        """Extracts min and max numbers from messy strings."""
        if pd.isna(value): return None, None
        nums = re.findall(r'\d+', str(value))
        if len(nums) >= 2:
            return int(nums[0]), int(nums[-1])
        elif len(nums) == 1:
            return int(nums[0]), int(nums[0])
        return None, None

    def fix_dates(self, value):
        """Standardizes messy dates to YYYY-MM-DD."""
        try:
            return parser.parse(str(value)).strftime('%Y-%m-%d')
        except:
            return value

    def process(self):
        """The main pipeline called by your FastAPI 'Heart'."""
        # This now correctly calls the indented load_data method
        self.load_data()
        
        # 1. Standardize Headers
        self.df.columns = self.df.columns.str.strip().str.lower().str.replace(" ", "_")

        # 2. Smart Cleaning Loop
        for col in self.df.columns:
            # Fix text columns
            if any(key in col for key in ['company', 'name', 'city', 'country']):
                self.df[col] = self.df[col].apply(self.clean_text)
            
            # Fix date columns
            elif 'date' in col:
                self.df[col] = self.df[col].apply(self.fix_dates)
            
            # Fix numeric range columns
            elif any(key in col for key in ['size', 'rate', 'price', 'team', 'cost']):
                new_cols = self.df[col].apply(lambda x: pd.Series(self.parse_numbers(x)))
                self.df[f'{col}_min'] = new_cols[0]
                self.df[f'{col}_max'] = new_cols[1]

        # 3. Final Polish
        self.df = self.df.dropna(how='all')
        
        return self.df