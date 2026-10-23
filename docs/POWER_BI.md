# Подключение к Power BI Desktop

Готовый `.pbix` в проект не входит. Для самостоятельной сборки отчёта импортируйте `data/processed/orders_mart.csv` через Text/CSV (UTF-8). Задайте `in_scope`, `delivered`, `delivery_eligible`, `late`, `low_review` как Logical с сохранением пустых значений; денежные поля BRL — Decimal Number; даты — Date/Time. Назовите таблицу `Orders`.

```dax
Eligible Orders = CALCULATE(COUNTROWS(Orders), Orders[delivery_eligible] = TRUE())
Late Orders = CALCULATE(COUNTROWS(Orders), Orders[delivery_eligible] = TRUE(), Orders[late] = TRUE())
Late Rate = DIVIDE([Late Orders], [Eligible Orders])
Merchandise BRL = CALCULATE(SUM(Orders[merchandise_brl]), Orders[in_scope] = TRUE(), Orders[delivered] = TRUE())
```

Страница обзора: карточки количества пригодных заказов, доли задержек и оборота; месячная динамика; количество задержек и их доля по штатам. Фильтры: месяц покупки и штат. Для отзывов используйте только пригодные заказы с непустой оценкой. Не применяйте фильтр `late = True` ко всему отчёту: это сделает знаменатель доли задержек некорректным.

Контрольные значения без фильтров: 96 203 пригодных заказа, 6 531 задержка, 6,78877%; оборот 13 181 027,13 BRL. DAX предоставлен как инструкция; Power BI Desktop в этой среде не запускался.
