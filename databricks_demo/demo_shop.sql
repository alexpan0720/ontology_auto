-- =====================================================================
-- Auto Ontology 演示数据：电商零售（demo_shop）
-- 在 Databricks SQL Editor 中整段执行（右上角选一个 SQL Warehouse，按 Ctrl+Shift+Enter 运行全部）。
--
-- 生成内容（数据是确定性的伪随机，重复执行结果一致，可重复运行）：
--   customers    300 行   客户
--   products      60 行   商品
--   orders      3000 行   订单（2025-01-01 ~ 2026-10-26）
--   order_items ~6000 行  订单明细
-- 表和字段都带中文注释，并声明了主键/外键（Unity Catalog 信息性约束），
-- Auto Ontology 会读取这些注释和约束来生成语义层。
-- =====================================================================

-- ① 改成你工作区里的 catalog 名称。先单独运行 SHOW CATALOGS; 查看。
--    免费版（Free Edition）一般叫 workspace；试用版通常是和工作区同名的 catalog。
USE CATALOG workspace;

CREATE SCHEMA IF NOT EXISTS demo_shop COMMENT '电商零售演示数据：客户、商品、订单、订单明细';
USE SCHEMA demo_shop;

-- 先删明细表再删被引用的表，保证脚本可以重复运行
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS customers;

-- ---------------------------------------------------------------------
-- 客户
-- ---------------------------------------------------------------------
CREATE TABLE customers (
  customer_id   BIGINT NOT NULL COMMENT '客户ID，主键',
  customer_name STRING COMMENT '客户姓名',
  gender        STRING COMMENT '性别：男 / 女',
  province      STRING COMMENT '所在省份',
  city          STRING COMMENT '所在城市',
  member_level  STRING COMMENT '会员等级：普通 / 银卡 / 金卡 / 钻石',
  signup_date   DATE   COMMENT '注册日期',
  CONSTRAINT pk_customers PRIMARY KEY (customer_id)
) COMMENT '客户信息表，每行一个注册客户';

INSERT INTO customers
SELECT
  id AS customer_id,
  concat(
    element_at(array('王','李','张','刘','陈','杨','赵','黄','周','吴','徐','孙'), CAST(pmod(hash(id, 'surname'), 12) + 1 AS INT)),
    element_at(array('伟','芳','娜','敏','静','磊','洋','勇','艳','杰','涛','明','超','秀英','丽','强','军','婷'), CAST(pmod(hash(id, 'given'), 18) + 1 AS INT))
  ) AS customer_name,
  IF(pmod(hash(id, 'gender'), 2) = 0, '男', '女') AS gender,
  element_at(array('北京','上海','广东','广东','浙江','浙江','江苏','四川','湖北','陕西'), CAST(pmod(hash(id, 'city'), 10) + 1 AS INT)) AS province,
  element_at(array('北京','上海','广州','深圳','杭州','宁波','南京','成都','武汉','西安'), CAST(pmod(hash(id, 'city'), 10) + 1 AS INT)) AS city,
  CASE
    WHEN pmod(hash(id, 'level'), 100) < 55 THEN '普通'
    WHEN pmod(hash(id, 'level'), 100) < 80 THEN '银卡'
    WHEN pmod(hash(id, 'level'), 100) < 95 THEN '金卡'
    ELSE '钻石'
  END AS member_level,
  date_add(DATE'2023-01-01', CAST(pmod(hash(id, 'signup'), 900) AS INT)) AS signup_date
FROM range(1, 301);

-- ---------------------------------------------------------------------
-- 商品
-- ---------------------------------------------------------------------
CREATE TABLE products (
  product_id   BIGINT        NOT NULL COMMENT '商品ID，主键',
  product_name STRING        COMMENT '商品名称',
  category     STRING        COMMENT '商品品类：手机 / 笔记本电脑 / 耳机 / 智能手表 / 平板电脑 / 家电',
  brand        STRING        COMMENT '品牌',
  unit_price   DECIMAL(10,2) COMMENT '标准售价（元）',
  cost_price   DECIMAL(10,2) COMMENT '采购成本价（元）',
  launch_date  DATE          COMMENT '上架日期',
  CONSTRAINT pk_products PRIMARY KEY (product_id)
) COMMENT '商品目录表，每行一个在售商品';

INSERT INTO products
SELECT
  product_id,
  concat(brand, ' ', category, ' ', model) AS product_name,
  category,
  brand,
  CAST(round(base_price * price_factor, 2) AS DECIMAL(10,2)) AS unit_price,
  CAST(round(base_price * price_factor * cost_ratio, 2) AS DECIMAL(10,2)) AS cost_price,
  date_add(DATE'2024-01-01', CAST(pmod(hash(product_id, 'launch'), 400) AS INT)) AS launch_date
FROM (
  SELECT
    id AS product_id,
    element_at(array('手机','笔记本电脑','耳机','智能手表','平板电脑','家电'), CAST(pmod(id, 6) + 1 AS INT)) AS category,
    element_at(array(3999.0, 6999.0, 599.0, 1499.0, 2999.0, 2499.0), CAST(pmod(id, 6) + 1 AS INT)) AS base_price,
    element_at(array('华为','小米','苹果','联想','OPPO','美的','荣耀','vivo'), CAST(pmod(hash(id, 'brand'), 8) + 1 AS INT)) AS brand,
    concat(element_at(array('Pro','Max','Lite','Air','Ultra','标准版'), CAST(pmod(hash(id, 'model'), 6) + 1 AS INT)), ' ', CAST(id AS STRING)) AS model,
    0.6 + pmod(hash(id, 'factor'), 90) / 100.0 AS price_factor,
    0.55 + pmod(hash(id, 'cost'), 25) / 100.0 AS cost_ratio
  FROM range(1, 61)
);

-- ---------------------------------------------------------------------
-- 订单
-- ---------------------------------------------------------------------
CREATE TABLE orders (
  order_id       BIGINT NOT NULL COMMENT '订单ID，主键',
  customer_id    BIGINT NOT NULL COMMENT '下单客户ID，关联 customers.customer_id',
  order_date     DATE   COMMENT '下单日期',
  channel        STRING COMMENT '下单渠道：线上商城 / 小程序 / 线下门店',
  status         STRING COMMENT '订单状态：已完成 / 已取消 / 已退货。统计销售额时通常只算已完成',
  payment_method STRING COMMENT '支付方式：微信支付 / 支付宝 / 银行卡',
  CONSTRAINT pk_orders PRIMARY KEY (order_id),
  CONSTRAINT fk_orders_customer FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
) COMMENT '订单头表，每行一个订单；金额在 order_items 明细中';

INSERT INTO orders
SELECT
  id AS order_id,
  pmod(hash(id, 'customer'), 300) + 1 AS customer_id,
  date_add(DATE'2025-01-01', CAST(pmod(hash(id, 'date'), 664) AS INT)) AS order_date,
  element_at(array('线上商城','线上商城','小程序','线下门店'), CAST(pmod(hash(id, 'channel'), 4) + 1 AS INT)) AS channel,
  CASE
    WHEN pmod(hash(id, 'status'), 100) < 85 THEN '已完成'
    WHEN pmod(hash(id, 'status'), 100) < 93 THEN '已取消'
    ELSE '已退货'
  END AS status,
  element_at(array('微信支付','支付宝','支付宝','银行卡'), CAST(pmod(hash(id, 'pay'), 4) + 1 AS INT)) AS payment_method
FROM range(100001, 103001);

-- ---------------------------------------------------------------------
-- 订单明细
-- ---------------------------------------------------------------------
CREATE TABLE order_items (
  order_item_id BIGINT        NOT NULL COMMENT '订单明细ID，主键',
  order_id      BIGINT        NOT NULL COMMENT '所属订单ID，关联 orders.order_id',
  product_id    BIGINT        NOT NULL COMMENT '商品ID，关联 products.product_id',
  quantity      INT           COMMENT '购买数量',
  unit_price    DECIMAL(10,2) COMMENT '成交单价（元）',
  discount_rate DECIMAL(4,2)  COMMENT '折扣率，0.10 表示打九折',
  line_amount   DECIMAL(12,2) COMMENT '明细实付金额（元）= 数量 × 成交单价 × (1 - 折扣率)',
  CONSTRAINT pk_order_items PRIMARY KEY (order_item_id),
  CONSTRAINT fk_order_items_order FOREIGN KEY (order_id) REFERENCES orders (order_id),
  CONSTRAINT fk_order_items_product FOREIGN KEY (product_id) REFERENCES products (product_id)
) COMMENT '订单明细表，每行是订单中的一个商品';

INSERT INTO order_items
SELECT
  order_item_id,
  order_id,
  product_id,
  quantity,
  unit_price,
  discount_rate,
  CAST(round(quantity * unit_price * (1 - discount_rate), 2) AS DECIMAL(12,2)) AS line_amount
FROM (
  SELECT
    o.order_id * 10 + n.id AS order_item_id,
    o.order_id,
    p.product_id,
    CAST(pmod(hash(o.order_id, n.id, 'qty'), 3) + 1 AS INT) AS quantity,
    p.unit_price,
    CAST(element_at(array(0.0, 0.0, 0.0, 0.05, 0.10, 0.20), CAST(pmod(hash(o.order_id, n.id, 'disc'), 6) + 1 AS INT)) AS DECIMAL(4,2)) AS discount_rate
  FROM orders o
  JOIN range(1, 4) n
    ON n.id <= pmod(hash(o.order_id, 'lines'), 3) + 1
  JOIN products p
    ON p.product_id = pmod(hash(o.order_id, n.id, 'product'), 60) + 1
);

-- ---------------------------------------------------------------------
-- 检查结果
-- ---------------------------------------------------------------------
SELECT 'customers' AS table_name, count(*) AS row_count FROM customers
UNION ALL SELECT 'products', count(*) FROM products
UNION ALL SELECT 'orders', count(*) FROM orders
UNION ALL SELECT 'order_items', count(*) FROM order_items;
