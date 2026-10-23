"""Order-level preparation and reproducible Olist delivery analysis."""
from pathlib import Path
import hashlib
import json
import sqlite3
import platform
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

START = pd.Timestamp('2017-01-01')
END = pd.Timestamp('2018-09-01')
MIN_STATE_ORDERS = 500
SOURCE_URL = 'https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce'
TABLES = {
    'customers': 'olist_customers_dataset.csv',
    'orders': 'olist_orders_dataset.csv',
    'items': 'olist_order_items_dataset.csv',
    'payments': 'olist_order_payments_dataset.csv',
    'reviews': 'olist_order_reviews_dataset.csv',
    'products': 'olist_products_dataset.csv',
    'sellers': 'olist_sellers_dataset.csv',
    'categories': 'product_category_name_translation.csv',
}
BLUE, ORANGE, GRAY = '#236894', '#BC642B', '#66717B'

def load_data(root):
    tables = {}
    for name, filename in TABLES.items():
        path = root / 'data/raw' / filename
        if not path.exists():
            raise FileNotFoundError(f'Missing {path}. Extract the Olist CSV files into data/raw.')
        tables[name] = pd.read_csv(path, dtype={
            'customer_zip_code_prefix': 'string', 'seller_zip_code_prefix': 'string'
        })
    return tables

def source_manifest(root):
    rows = []
    for path in sorted((root/'data/raw').glob('*.csv')):
        rows.append({'file':path.name, 'bytes':path.stat().st_size,
                     'sha256':hashlib.sha256(path.read_bytes()).hexdigest(), 'source_url':SOURCE_URL})
    return pd.DataFrame(rows)

def prepare(tables):
    data = {name: df.copy() for name, df in tables.items()}
    quality = []
    def check(table, metric, value, interpretation='diagnostic'):
        quality.append({'table':table,'check':metric,'count':int(value),'interpretation':interpretation})
    for name, df in data.items():
        check(name,'rows',len(df),'inventory')
        check(name,'full_duplicate_rows',df.duplicated().sum())
        for col in df:
            check(name,f'missing:{col}',df[col].isna().sum())
    for name, key in [('orders','order_id'),('customers','customer_id'),('products','product_id'),('sellers','seller_id'),('categories','product_category_name')]:
        check(name,f'duplicate_key:{key}',data[name][key].duplicated().sum(),'must_be_zero')
        if data[name][key].isna().any() or not data[name][key].is_unique:
            raise ValueError(f'{name}.{key} must be non-null and unique')
    for name, keys in [('items',['order_id','order_item_id']),('payments',['order_id','payment_sequential'])]:
        if data[name][keys].isna().any().any() or data[name].duplicated(keys).any():
            raise ValueError(f'{name}: invalid composite key')
    for child, col, parent, parent_col in [
        ('orders','customer_id','customers','customer_id'),('items','order_id','orders','order_id'),
        ('payments','order_id','orders','order_id'),('reviews','order_id','orders','order_id'),
        ('items','product_id','products','product_id'),('items','seller_id','sellers','seller_id')]:
        missing = ~data[child][col].isin(data[parent][parent_col])
        check(child,f'unmatched:{col}->{parent}',missing.sum(),'must_be_zero')
        if missing.any(): raise ValueError(f'Unmatched relationship {child}->{parent}')
    for name, cols in {
        'orders':['order_purchase_timestamp','order_approved_at','order_delivered_carrier_date','order_delivered_customer_date','order_estimated_delivery_date'],
        'reviews':['review_creation_date','review_answer_timestamp'],
        'items':['shipping_limit_date']}.items():
        for col in cols:
            original=data[name][col]
            parsed=pd.to_datetime(original, errors='coerce')
            check(name,f'invalid_date:{col}',(original.notna() & parsed.isna()).sum())
            data[name][col]=parsed
    for name, col in [('items','price'),('items','freight_value'),('payments','payment_value')]:
        values=pd.to_numeric(data[name][col],errors='coerce')
        if values.isna().any() or (values<0).any(): raise ValueError(f'Invalid money {name}.{col}')
        cents=(values*100).round()
        if not np.allclose(values*100,cents): raise ValueError('Money has more than two decimal places')
        data[name][col+'_cents']=cents.astype('int64')
    items=(data['items'].groupby('order_id',as_index=False)
           .agg(item_count=('order_item_id','size'),seller_count=('seller_id','nunique'),
                merchandise_cents=('price_cents','sum'),freight_cents=('freight_value_cents','sum')))
    payments=(data['payments'].groupby('order_id',as_index=False)
              .agg(payment_count=('payment_sequential','size'),payment_cents=('payment_value_cents','sum')))
    reviews=data['reviews'].copy()
    if not reviews.review_score.between(1,5).all(): raise ValueError('Invalid review score')
    reviews['_source_row']=np.arange(len(reviews))
    review_order=['order_id','review_answer_timestamp','review_creation_date','review_id','_source_row']
    ordered=reviews.sort_values(review_order,na_position='first',kind='stable')
    latest=ordered.drop_duplicates('order_id',keep='last')
    first=ordered.drop_duplicates('order_id',keep='first')[['order_id','review_score']].rename(columns={'review_score':'first_review_score'})
    review_count=reviews.groupby('order_id').size().rename('review_count')
    selected=latest[['order_id','review_score','review_answer_timestamp']].merge(first,on='order_id',validate='one_to_one')
    selected=selected.merge(review_count,on='order_id',validate='one_to_one')
    check('reviews','extra_rows_per_order',reviews.order_id.duplicated().sum(),'resolved_by_latest_answer')
    mart=data['orders'].merge(data['customers'],on='customer_id',how='left',validate='many_to_one')
    for frame in [items,payments,selected]:
        mart=mart.merge(frame,on='order_id',how='left',validate='one_to_one')
    assert len(mart)==len(data['orders']) and mart.order_id.is_unique
    for col in ['item_count','seller_count','payment_count','review_count']:
        mart[col]=mart[col].fillna(0).astype(int)
    for col in ['merchandise_cents','freight_cents','payment_cents','review_score','first_review_score']:
        mart[col]=mart[col].astype('Int64')
    for col in ['merchandise','freight','payment']:
        mart[col+'_brl']=mart[col+'_cents']/100
    mart['in_scope']=mart.order_purchase_timestamp.ge(START) & mart.order_purchase_timestamp.lt(END)
    mart['purchase_month']=mart.order_purchase_timestamp.dt.strftime('%Y-%m')
    mart['delivered']=mart.order_status.eq('delivered')
    required=['order_purchase_timestamp','order_delivered_customer_date','order_estimated_delivery_date']
    has_dates=mart[required].notna().all(axis=1)
    chronological=(mart.order_delivered_customer_date.ge(mart.order_purchase_timestamp) &
                   mart.order_estimated_delivery_date.ge(mart.order_purchase_timestamp.dt.normalize()))
    mart['delivery_valid']=mart.delivered & has_dates & chronological
    mart['delivery_eligible']=mart.in_scope & mart.delivery_valid
    mart['delivery_days']=(mart.order_delivered_customer_date-mart.order_purchase_timestamp).dt.total_seconds()/86400
    mart['delay_days']=(mart.order_delivered_customer_date.dt.normalize()-mart.order_estimated_delivery_date.dt.normalize()).dt.days.astype('Int64')
    mart['late']=mart.delay_days.gt(0).where(mart.delivery_valid).astype('boolean')
    mart['low_review']=mart.review_score.le(2).where(mart.review_score.notna()).astype('boolean')
    mart['review_after_delivery']=(mart.review_answer_timestamp.ge(mart.order_delivered_customer_date) & mart.review_answer_timestamp.notna())
    mart['payment_difference_cents']=mart.payment_cents-mart.merchandise_cents-mart.freight_cents
    check('orders','delivered_missing_required_dates',(mart.delivered & ~has_dates).sum(),'excluded_from_delivery_metrics')
    check('orders','delivered_invalid_chronology',(mart.delivered & has_dates & ~chronological).sum(),'excluded_from_delivery_metrics')
    check('orders','carrier_before_approval',(mart.order_delivered_carrier_date<mart.order_approved_at).sum(),'not_used_to_filter_total_delivery_duration')
    check('orders','delivered_no_items',(mart.delivered & mart.item_count.eq(0)).sum())
    check('orders','no_payments',mart.payment_count.eq(0).sum())
    check('orders','no_reviews',mart.review_count.eq(0).sum())
    check('orders','payment_vs_items_difference_over_1_cent',mart.payment_difference_cents.abs().gt(1).sum(),'reported_not_corrected')
    check('orders','reviews_answered_before_delivery',(mart.review_score.notna() & mart.delivery_valid & ~mart.review_after_delivery).sum(),'sensitivity_analysis')
    assert int(mart.merchandise_cents.sum())==int(data['items'].price_cents.sum())
    assert int(mart.payment_cents.sum())==int(data['payments'].payment_value_cents.sum())
    return mart,pd.DataFrame(quality),data

def wilson(successes,n):
    p=np.asarray(successes,dtype=float)/np.asarray(n,dtype=float)
    n=np.asarray(n,dtype=float); z=1.95996398454
    center=(p+z*z/(2*n))/(1+z*z/n)
    half=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
    return center-half,center+half

def group_reviews(frame,group):
    covered=frame[frame.review_score.notna()].copy()
    result=covered.groupby(group,observed=True).agg(
        reviewed_orders=('order_id','size'),mean_review=('review_score','mean'),
        low_reviews=('low_review','sum')).reset_index()
    result['low_review_rate']=result.low_reviews/result.reviewed_orders
    result['low_ci'],result['high_ci']=wilson(result.low_reviews,result.reviewed_orders)
    return result

def summarize(mart,quality):
    scope=mart[mart.in_scope].copy()
    delivered=scope[scope.delivered].copy()
    eligible=scope[scope.delivery_eligible].copy()
    reviewed=eligible[eligible.review_score.notna()].copy()
    state=eligible.groupby('customer_state').agg(orders=('order_id','size'),late_orders=('late','sum'),
        median_delivery_days=('delivery_days','median')).reset_index()
    state['late_rate']=state.late_orders/state.orders
    state['low_ci'],state['high_ci']=wilson(state.late_orders,state.orders)
    state['ranking_eligible']=state.orders.ge(MIN_STATE_ORDERS)
    state=state.sort_values('late_orders',ascending=False)
    monthly=scope.groupby('purchase_month').agg(orders=('order_id','size'),delivered_orders=('delivered','sum'))
    monthly=monthly.join(eligible.groupby('purchase_month').agg(eligible_orders=('order_id','size'),late_orders=('late','sum')))
    monthly=monthly.join(delivered.groupby('purchase_month').agg(merchandise_cents=('merchandise_cents','sum')))
    monthly['merchandise_brl']=monthly.merchandise_cents/100
    monthly['late_rate']=monthly.late_orders/monthly.eligible_orders
    monthly['orders_mom_pct']=monthly.orders.pct_change()*100
    monthly=monthly.reset_index()
    reviews=group_reviews(eligible,'late')
    reviews=reviews.merge(eligible.groupby('late').size().rename('eligible_orders'),on='late',validate='one_to_one')
    reviews['review_coverage']=reviews.reviewed_orders/reviews.eligible_orders
    eligible['delay_bucket']=pd.cut(eligible.delay_days.astype(float),[-np.inf,0,3,7,14,np.inf],labels=['On time','1-3 days','4-7 days','8-14 days','15+ days'])
    delay=group_reviews(eligible,'delay_bucket')
    sensitivities=[]
    for label,frame,score in [
        ('Latest review',eligible,'review_score'),('First review',eligible,'first_review_score'),
        ('Only answers after delivery',eligible[eligible.review_after_delivery],'review_score'),
        ('Exclude Aug 2018',eligible[eligible.purchase_month.ne('2018-08')],'review_score')]:
        frame=frame[frame[score].notna()]
        rate=frame.assign(low=frame[score].le(2)).groupby('late').low.agg(['mean','size'])
        sensitivities.append({'definition':label,'on_time_n':int(rate.loc[False,'size']),
            'late_n':int(rate.loc[True,'size']),'on_time_low_rate':float(rate.loc[False,'mean']),
            'late_low_rate':float(rate.loc[True,'mean']),'difference_pp':float((rate.loc[True,'mean']-rate.loc[False,'mean'])*100)})
    strata=reviewed.groupby(['customer_state','purchase_month','late']).agg(n=('order_id','size'),low_rate=('low_review','mean')).unstack('late')
    strata=strata[(strata[('n',False)]>=10)&(strata[('n',True)]>=10)].copy()
    weights=strata[('n',False)]+strata[('n',True)]
    adjusted=float(np.average((strata[('low_rate',True)]-strata[('low_rate',False)]).astype(float),weights=weights.astype(float))*100)
    review_gap=sensitivities[0]['difference_pp']
    summary={
        'scope_start':'2017-01-01','scope_end_inclusive':'2018-08-31','source_orders':len(mart),
        'purchase_min':str(mart.order_purchase_timestamp.min()),'purchase_max':str(mart.order_purchase_timestamp.max()),
        'scope_orders':len(scope),'delivered_orders':len(delivered),'delivery_eligible_orders':len(eligible),
        'delivery_excluded_orders':len(delivered)-len(eligible),'late_orders':int(eligible.late.sum()),
        'late_rate':float(eligible.late.mean()),'median_delivery_days':float(eligible.delivery_days.median()),
        'p90_delivery_days':float(eligible.delivery_days.quantile(.9)),
        'merchandise_brl':float(delivered.merchandise_cents.sum()/100),
        'average_merchandise_order_brl':float(delivered.merchandise_cents.mean()/100),
        'payment_brl_delivered':float(delivered.payment_cents.sum()/100),
        'reviewed_orders':len(reviewed),'review_coverage':len(reviewed)/len(eligible),
        'low_review_gap_pp':review_gap,'state_month_standardized_gap_pp':adjusted,
        'standardized_strata':len(strata),'standardized_orders':int(weights.sum()),
        'repeat_delivered_buyers':int(delivered.groupby('customer_unique_id').size().gt(1).sum()),
        'delivered_buyers':int(delivered.customer_unique_id.nunique()),
    }
    status=scope.order_status.value_counts().rename_axis('status').reset_index(name='orders')
    return summary,{'quality_checks':quality,'state_delivery':state,'monthly_metrics':monthly,
                    'review_comparison':reviews,'delay_buckets':delay,'sensitivity':pd.DataFrame(sensitivities),'order_status':status}

def plot_results(mart,tables):
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,
                         'axes.spines.right':False,'axes.titleweight':'bold','figure.facecolor':'white'})
    figures={}
    monthly=tables['monthly_metrics']; dates=pd.to_datetime(monthly.purchase_month)
    fig,axes=plt.subplots(2,1,figsize=(11,7),sharex=True,layout='constrained')
    axes[0].plot(dates,monthly.orders,color=BLUE,marker='o',markersize=4)
    axes[0].set(title='Monthly orders and delivery delays | Jan 2017-Aug 2018',ylabel='All orders')
    axes[1].plot(dates,monthly.late_rate.astype(float)*100,color=ORANGE,marker='o',markersize=4)
    axes[1].set(ylabel='Late deliveries (%)',xlabel='Purchase month',ylim=(0,None))
    axes[1].set_xticks(dates.iloc[::3].tolist())
    axes[1].set_xticklabels([d.strftime('%b %Y') for d in dates.iloc[::3].tolist()])
    for ax in axes: ax.grid(axis='y',alpha=.18)
    figures['01_monthly_orders_and_delays']=fig
    state=tables['state_delivery'].query('ranking_eligible').head(10).sort_values('late_orders')
    fig,ax=plt.subplots(figsize=(10,6),layout='constrained')
    ax.barh(state.customer_state,state.late_orders.astype(int),color=BLUE)
    for i,(_,r) in enumerate(state.iterrows()):
        ax.text(float(r.late_orders)+20,i,f'{int(r.late_orders):,} / {int(r.orders):,} ({r.late_rate:.1%})',va='center',fontsize=10)
    ax.set(title='States with most late deliveries | Jan 2017-Aug 2018',xlabel='Late delivered orders',ylabel='State',xlim=(0,float(state.late_orders.max())*1.55))
    ax.grid(axis='x',alpha=.18)
    figures['02_state_priorities']=fig
    groups=tables['review_comparison'].sort_values('late')
    fig,ax=plt.subplots(figsize=(8,5),layout='constrained')
    rates=groups.low_review_rate.astype(float).to_numpy()*100
    low=groups.low_ci.to_numpy()*100; high=groups.high_ci.to_numpy()*100
    ax.bar(['On time','Late'],rates,color=[BLUE,ORANGE],width=.55)
    ax.errorbar([0,1],rates,yerr=[rates-low,high-rates],fmt='none',ecolor='#222222',capsize=5)
    for i,(_,r) in enumerate(groups.iterrows()):
        ax.text(i,r.low_review_rate*100+3,f'{r.low_review_rate:.1%}\nn={int(r.reviewed_orders):,}',ha='center')
    ax.set(title='Low ratings (1-2 stars) by delivery timing',ylabel='Share of reviewed orders (%)',ylim=(0,min(100,max(rates)+17)))
    ax.grid(axis='y',alpha=.18)
    figures['03_reviews_and_delays']=fig
    bucket=tables['delay_buckets']
    fig,ax=plt.subplots(figsize=(10,5),layout='constrained')
    x=np.arange(len(bucket)); rates=bucket.low_review_rate.astype(float).to_numpy()*100
    ax.plot(x,rates,color=ORANGE,marker='o')
    ax.errorbar(x,rates,yerr=[rates-bucket.low_ci.to_numpy()*100,bucket.high_ci.to_numpy()*100-rates],fmt='none',ecolor=ORANGE,capsize=4)
    ax.set_xticks(x,[f'{r.delay_bucket}\nn={int(r.reviewed_orders):,}' for _,r in bucket.iterrows()])
    ax.set(title='Low ratings by delivery delay',ylabel='Share of reviewed orders rated 1-2 (%)',xlabel='Calendar days after promised date',ylim=(0,100))
    ax.grid(axis='y',alpha=.18)
    figures['04_delay_severity']=fig
    duration=np.sort(mart.loc[mart.delivery_eligible,'delivery_days'].to_numpy())
    fig,ax=plt.subplots(figsize=(10,5),layout='constrained')
    ax.plot(duration,np.arange(1,len(duration)+1)/len(duration)*100,color=BLUE)
    for q in [.5,.9]:
        value=float(np.quantile(duration,q)); ax.plot(value,q*100,'o',color=ORANGE)
        ax.annotate(f'P{int(q*100)}: {value:.1f} days',(value,q*100),xytext=(12,-20 if q==.9 else 12),textcoords='offset points')
    ax.set(title='Delivery time distribution | All valid delivered orders in scope',xlabel='Elapsed days from purchase to delivery',ylabel='Cumulative share (%)',xlim=(0,float(duration.max())*1.02),ylim=(0,102))
    ax.grid(alpha=.18)
    figures['05_delivery_duration']=fig
    return figures

def export_results(root,mart,summary,tables,figures,raw):
    out=root/'reports'; (out/'figures').mkdir(parents=True,exist_ok=True); (out/'tables').mkdir(exist_ok=True)
    for name,frame in tables.items(): frame.to_csv(out/'tables'/f'{name}.csv',index=False,encoding='utf-8-sig')
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    for name,fig in figures.items(): fig.savefig(out/'figures'/f'{name}.png',dpi=150,bbox_inches='tight')
    processed=root/'data/processed'; processed.mkdir(parents=True,exist_ok=True)
    mart.to_csv(processed/'orders_mart.csv',index=False,encoding='utf-8-sig')
    source_manifest(root).to_csv(out/'source_manifest.csv',index=False)
    db=processed/'olist.sqlite'
    with sqlite3.connect(db) as con:
        for name in ['orders','items','payments']:
            raw[name].to_sql(name,con,if_exists='replace',index=False)
        sql_mart=mart.copy()
        for col in sql_mart.select_dtypes(include=['boolean','bool']): sql_mart[col]=sql_mart[col].astype('Int64')
        sql_mart.to_sql('orders_mart',con,if_exists='replace',index=False)
        con.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_mart_id ON orders_mart(order_id)')
        for path in sorted((root/'sql').glob('*.sql')):
            frame=pd.read_sql_query(path.read_text(encoding='utf-8'),con)
            frame.to_csv(out/'tables'/f'sql_{path.stem}.csv',index=False,encoding='utf-8-sig')
            if path.name.startswith('01_'):
                assert frame.order_id.is_unique and len(frame)==len(mart)
                assert int(frame.merchandise_cents.sum())==int(mart.merchandise_cents.sum())
                assert int(frame.payment_cents.sum())==int(mart.payment_cents.sum())
            if path.name.startswith('02_'):
                assert int(frame.eligible_orders.sum())==summary['delivery_eligible_orders']
                assert int(frame.late_orders.sum())==summary['late_orders']
            if path.name.startswith('03_'):
                assert int(frame.orders.sum())==summary['scope_orders']
            if path.name.startswith('04_'):
                assert int(frame.reviewed_orders.sum())==summary['reviewed_orders']
    versions={'python':platform.python_version(),'pandas':pd.__version__,'numpy':np.__version__,'sqlite':sqlite3.sqlite_version}
    (out/'validation.json').write_text(json.dumps({'status':'passed','checks':[
        'Unique keys and referential integrity','One row per order after all joins',
        'Exact integer-cent reconciliation of merchandise and payments',
        'All SQL queries executed on SQLite','SQL/Python count and amount reconciliations'],
        'environment':versions},indent=2),encoding='utf-8')

def run(root):
    raw=load_data(root)
    mart,quality,prepared=prepare(raw)
    summary,tables=summarize(mart,quality)
    figures=plot_results(mart,tables)
    export_results(root,mart,summary,tables,figures,prepared)
    return mart,summary,tables,figures
