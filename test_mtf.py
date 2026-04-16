from mtf_analysis import analyze_multi_timeframe
r = analyze_multi_timeframe('BBCA.JK')
print('Confluence:', r['confluence'], '| Score:', r['confluence_score'])
print('Summary:', r['summary'])
for k in ['weekly', 'daily', 'intraday']:
    tf = r[k]
    print(f"  {k}: bias={tf.get('bias','N/A')} rsi={tf.get('rsi','N/A')} status={tf.get('status','N/A')}")
