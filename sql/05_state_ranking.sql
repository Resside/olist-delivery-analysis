WITH states AS (
    SELECT customer_state, COUNT(*) AS eligible_orders, SUM(late) AS late_orders,
           1.0*SUM(late)/COUNT(*) AS late_rate
    FROM orders_mart WHERE delivery_eligible=1
    GROUP BY customer_state HAVING COUNT(*)>=500
)
SELECT *, DENSE_RANK() OVER (ORDER BY late_orders DESC) AS volume_rank,
       DENSE_RANK() OVER (ORDER BY late_rate DESC) AS rate_rank
FROM states ORDER BY volume_rank;
