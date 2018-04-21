"""
Example to demonstrate creating a pivot table from the output of zonal stats CLI
"""

import time
import pandas


# Return a pipe-delimited combination of value from every column up through zone
def get_key(row):
    key_parts = []
    for col in row.keys():
        if col == 'zone':
            return '|'.join(key_parts)

        key_parts.append(str(row[col]))


start = time.time()

infilename = '/tmp/test.csv'
df = pandas.read_csv(infilename)
df['key'] = df.apply(lambda x: get_key(x), axis=1)
sub_df = df[['key', 'zone', 'mean']]
pivot = sub_df.pivot('zone', columns='key')

# Need to manually create the CSV instead of letting pandas do it, due to composite header
# we don't want
with open('/tmp/pivot.csv', 'w') as outfile:
    header = ','.join( ['zone'] + pivot.columns.levels[1].tolist())
    csv_data = pivot.to_csv(None, index=True, header=False)
    outfile.write(header + '\n' + csv_data)

print('Elapsed: {0:.2f}'.format(time.time() - start))