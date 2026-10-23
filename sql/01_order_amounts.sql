-- Aggregate each one-to-many source before joining to orders.
WITH item_totals AS (
    SELECT order_id, COUNT(*) AS item_count,
           SUM(price_cents) AS merchandise_cents,
           SUM(freight_value_cents) AS freight_cents
    FROM items GROUP BY order_id
), payment_totals AS (
    SELECT order_id, COUNT(*) AS payment_count,
           SUM(payment_value_cents) AS payment_cents
    FROM payments GROUP BY order_id
)
SELECT o.order_id, o.order_status, i.item_count, i.merchandise_cents,
       i.freight_cents, p.payment_count, p.payment_cents,
       p.payment_cents-i.merchandise_cents-i.freight_cents AS difference_cents
FROM orders o
LEFT JOIN item_totals i ON o.order_id=i.order_id
LEFT JOIN payment_totals p ON o.order_id=p.order_id;
