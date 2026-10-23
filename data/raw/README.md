# Подготовка исходных данных

Датасет не включён в GitHub-архив. Сохранённые результаты доступны без его скачивания; исходные CSV нужны для пересчёта.

1. Скачайте Brazilian E-Commerce Public Dataset by Olist: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce.
2. Распакуйте CSV непосредственно в `data/raw/`, без дополнительной вложенной папки. Можно скопировать эти CSV из ранее подготовленного локального проекта.
3. В окружении проекта выполните `python run_analysis.py` из корня репозитория.

Обязательные файлы:

- olist_customers_dataset.csv
- olist_orders_dataset.csv
- olist_order_items_dataset.csv
- olist_order_payments_dataset.csv
- olist_order_reviews_dataset.csv
- olist_products_dataset.csv
- olist_sellers_dataset.csv
- product_category_name_translation.csv

olist_geolocation_dataset.csv не участвует в расчётах. Исходный manifest включает и его контрольную сумму, поскольку первоначальная проверка выполнялась на полном наборе из девяти CSV. При пересчёте manifest отражает фактически присутствующие файлы.

Контрольные суммы первоначальных данных: `reports/source_manifest.csv`. Лицензия и атрибуция: `docs/DATA_LICENSE.md`. Исходные данные не изменяются скриптом; крупная витрина и SQLite восстанавливаются автоматически.
