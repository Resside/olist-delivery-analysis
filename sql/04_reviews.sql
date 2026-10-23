SELECT late, COUNT(*) AS reviewed_orders, ROUND(AVG(review_score),3) AS mean_review,
       SUM(CASE WHEN review_score<=2 THEN 1 ELSE 0 END) AS low_reviews,
       ROUND(100.0*SUM(CASE WHEN review_score<=2 THEN 1 ELSE 0 END)/COUNT(*),2) AS low_review_pct
FROM orders_mart WHERE delivery_eligible=1 AND review_score IS NOT NULL
GROUP BY late;
