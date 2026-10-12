import pandas as pd
import numpy as np
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
base = project_root / 'fabio_trade_flows' / 'data'
output_dir = project_root / 'data' / 'supplementary_tables'
output_dir.mkdir(parents=True, exist_ok=True)
blue_file = base / 'blue_fabio_water_all_2021.csv'
green_file = base / 'green_fabio_water_all_2021.csv'
region_file = base / 'country_region_map.xlsx'

regions = pd.read_excel(region_file)
regions.columns = [c.strip() for c in regions.columns]

REGION_ORDER = ['India','Pakistan','Southeast Asia','Rest of Asia','Africa','South America','Oceania','North America','Europe','Eurasia','Central America']
sub_to_region8 = {
    'Western Europe':'Europe','Northern Europe':'Europe','Southern Europe':'Europe','Southwestern Europe':'Europe','Eastern Europe':'Europe','Central Europe':'Europe','Southeast Europe':'Europe','European Union':'Europe','North Africa':'Africa','West Africa':'Africa','Central Africa':'Africa','East Africa':'Africa','Southeast Africa':'Africa','Southern Africa':'Africa','South Asia':'Rest of Asia','Southeast Asia':'Southeast Asia','East Asia':'Rest of Asia','East Asia (Special Administrative Region of China)':'Rest of Asia','Western Asia':'Rest of Asia','Middle East':'Rest of Asia','Middle East - Levant':'Rest of Asia','Middle East - Arabian Peninsula':'Rest of Asia','Middle East - Southwestern Asia':'Rest of Asia','Central Asia':'Rest of Asia','South Caucasus (Southwestern Asia)':'Rest of Asia','South America':'South America','Central America':'Central America','Caribbean':'Central America','North America':'North America','Oceania':'Oceania','Polynesia':'Oceania','Micronesia':'Oceania','Melanesia':'Oceania','Pacific':'Oceania','Indian Ocean':'Oceania','North Atlantic':'Europe','South Atlantic Ocean':'South America','Eurasia':'Eurasia','Eastern Europe and Northern Asia':'Eurasia',
}

def region8_map(regions_df):
    tmp = regions_df[['ISO','Region']].drop_duplicates().copy()
    def to_region8(iso, label):
        if pd.isna(iso) or pd.isna(label):
            return np.nan
        iso = str(iso).strip().upper()
        if iso == 'IND':
            return 'India'
        if iso == 'PAK':
            return 'Pakistan'
        s = str(label).strip()
        if s in REGION_ORDER:
            return s
        if s in sub_to_region8:
            return sub_to_region8[s]
        low = s.lower()
        if 'eurasia' in low or ('northern asia' in low and 'europe' in low):
            return 'Eurasia'
        if 'europe' in low:
            return 'Europe'
        if 'africa' in low:
            return 'Africa'
        if 'southeast asia' in low:
            return 'Southeast Asia'
        if any(k in low for k in ['asia','middle east','levant','arabian']):
            return 'Rest of Asia'
        if any(k in low for k in ['oceania','polynesia','micronesia','melanesia','pacific']):
            return 'Oceania'
        if 'south america' in low:
            return 'South America'
        if 'central america' in low or 'caribbean' in low:
            return 'Central America'
        if 'north america' in low:
            return 'North America'
        return np.nan
    tmp['Region8'] = tmp.apply(lambda row: to_region8(row['ISO'], row['Region']), axis=1)
    return tmp[['ISO','Region8']]

reg_map_df = region8_map(regions)

for kind, file_path, value_col, out_name in [
    ('blue', blue_file, 'blue_m3', 'supplementary_bluewater_region_flows_2021.csv'),
    ('green', green_file, 'green_m3', 'supplementary_greenwater_region_flows_2021.csv')
]:
    df = pd.read_csv(file_path)
    df.columns = [c.strip() for c in df.columns]
    df = df[df['fabio_com_order'].astype(str).str.lower().isin(['c015','c016'])].copy()
    code_map = df[['fabio_country_order','fabio_country']].drop_duplicates().rename(columns={'fabio_country_order':'consumer_code','fabio_country':'consumer_iso'})
    flow_cols = [c for c in df.columns if str(c).startswith('R')]
    base_df = df[['fabio_country'] + flow_cols].copy().rename(columns={'fabio_country':'producer_iso'})
    long_df = base_df.melt(id_vars='producer_iso', var_name='consumer_code', value_name=value_col)
    long_df['consumer_code'] = long_df['consumer_code'].astype(str)
    long_df[value_col] = pd.to_numeric(long_df[value_col], errors='coerce')
    long_df = long_df.replace([np.inf, -np.inf], np.nan).dropna(subset=[value_col])
    long_df = long_df[long_df[value_col] > 0]
    long_df = (
        long_df
        .merge(reg_map_df.rename(columns={'Region8':'producer_region'}), left_on='producer_iso', right_on='ISO', how='left')
        .drop(columns=['ISO'])
        .merge(code_map, on='consumer_code', how='left')
        .merge(reg_map_df.rename(columns={'Region8':'consumer_region'}), left_on='consumer_iso', right_on='ISO', how='left')
        .drop(columns=['ISO'])
    )
    long_df[['producer_region','consumer_region']] = long_df[['producer_region','consumer_region']].replace({'Central Americe':'Central America','South Americe':'South America'})
    long_df = long_df.dropna(subset=['producer_region','consumer_region'])
    result = long_df.groupby(['producer_region','consumer_region'], as_index=False).agg(**{value_col: (value_col, 'sum')})
    result = result.sort_values(['producer_region','consumer_region']).reset_index(drop=True)
    out_path = output_dir / out_name
    result.to_csv(out_path, index=False)
    print(f'{kind}: wrote {out_path}')

print('done')
