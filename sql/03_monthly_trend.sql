WITH monthly AS (
    SELECT purchase_month, COUNT(*) AS orders,
           SUM(delivered) AS delivered_orders,
           SUM(CASE WHEN delivered=1 THEN merchandise_cents ELSE 0 END)/100.0 AS merchandise_brl
    FROM orders_mart WHERE in_scope=1 GROUP BY purchase_month
), previous AS (
    SELECT *, LAG(orders) OVER (ORDER BY purchase_month) AS previous_month_orders
    FROM monthly
)
SELECT *, ROUND(100.0*(orders-previous_month_orders)/NULLIF(previous_month_orders,0),2) AS orders_mom_pct
FROM previous ORDER BY purchase_month;
