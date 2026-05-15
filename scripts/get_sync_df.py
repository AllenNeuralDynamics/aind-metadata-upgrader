"""Script to get sync dataframe and print upgrade status summary"""
from zombie_squirrel import custom

from aind_metadata_upgrader.sync import TABLE_NAME

df = custom(TABLE_NAME)

# Overall Statistics
print("=" * 70)
print("UPGRADE STATE SUMMARY")
print("=" * 70)
print(f"\nTotal records: {len(df):,}")

# Status breakdown
status_counts = df['status'].value_counts()
success_count = status_counts.get('success', 0)
failed_count = status_counts.get('failed', 0)
success_pct = (success_count / len(df)) * 100
failed_pct = (failed_count / len(df)) * 100

print(f"\n✓ Successful: {success_count:,} ({success_pct:.1f}%)")
print(f"✗ Failed:     {failed_count:,} ({failed_pct:.1f}%)")

# Version breakdown with success rates
print("\n" + "-" * 70)
print("BREAKDOWN BY UPGRADER VERSION")
print("-" * 70)

version_stats = df.groupby('upgrader_version').agg({
    'status': lambda x: (x == 'success').sum(),
    'v1_id': 'count'
}).rename(columns={'status': 'success_count', 'v1_id': 'total_count'})

version_stats['failed_count'] = version_stats['total_count'] - version_stats['success_count']
version_stats['success_rate'] = (version_stats['success_count'] / version_stats['total_count'] * 100).round(1)
version_stats = version_stats.sort_values('total_count', ascending=False)

for version, row in version_stats.iterrows():
    success_rate = row['success_rate']
    status_indicator = "✓" if success_rate >= 95 else "⚠" if success_rate >= 80 else "✗"
    print(f"  {status_indicator} v{version}: {int(row['total_count']):>6,} total | "
          f"{int(row['success_count']):>6,} success | {int(row['failed_count']):>6,} failed | "
          f"{success_rate:>5.1f}%")

# Records without v2_id (failed to generate v2)
no_v2 = df['v2_id'].isna().sum()
print(f"\nRecords without v2_id: {no_v2:,}")

print("\n" + "=" * 70)
