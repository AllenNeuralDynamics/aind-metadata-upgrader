"""Script to get sync dataframe and print the head"""
from zombie_squirrel import custom

from aind_metadata_upgrader.sync import REDSHIFT_TABLE_NAME

df = custom(REDSHIFT_TABLE_NAME)

print(df.head())
