-- Denominator: valid delivered orders purchased in the analysis period.
SELECT customer_state, COUNT(*) AS eligible_orders, SUM(late) AS late_orders,
       ROUND(100.0*SUM(late)/COUNT(*),2) AS late_pct,
       ROUND(AVG(delivery_days),2) AS mean_delivery_days
FROM orders_mart WHERE delivery_eligible=1
GROUP BY customer_state ORDER BY late_orders DESC;
