"""Script to get sync dataframe and print the head"""
from zombie_squirrel import custom

from aind_metadata_upgrader.sync import TABLE_NAME

df = custom(TABLE_NAME)

print(df.head())
