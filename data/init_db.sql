-- 智能问数Agent演示数据库初始化脚本
-- 创建电商数据库表结构

-- 用户表
CREATE TABLE users (
    user_id    SERIAL PRIMARY KEY,
    username   VARCHAR(50) NOT NULL,
    email      VARCHAR(100),
    phone      VARCHAR(20),
    city       VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 产品表
CREATE TABLE products (
    product_id   SERIAL PRIMARY KEY,
    product_name VARCHAR(100) NOT NULL,
    category     VARCHAR(50),
    price        DECIMAL(10, 2),
    stock        INT DEFAULT 0,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 订单表
CREATE TABLE orders (
    order_id    SERIAL PRIMARY KEY,
    user_id     INT REFERENCES users(user_id),
    order_date  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_amount DECIMAL(12, 2),
    status      VARCHAR(20) DEFAULT 'pending'
);

-- 订单明细表
CREATE TABLE order_items (
    item_id    SERIAL PRIMARY KEY,
    order_id   INT REFERENCES orders(order_id),
    product_id INT REFERENCES products(product_id),
    quantity   INT NOT NULL,
    unit_price DECIMAL(10, 2) NOT NULL
);

-- 商品评价表
CREATE TABLE reviews (
    review_id  SERIAL PRIMARY KEY,
    user_id    INT REFERENCES users(user_id),
    product_id INT REFERENCES products(product_id),
    rating     INT CHECK (rating BETWEEN 1 AND 5),
    comment    TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 添加注释
COMMENT ON TABLE users IS '用户信息表';
COMMENT ON TABLE products IS '产品信息表';
COMMENT ON TABLE orders IS '订单表';
COMMENT ON TABLE order_items IS '订单明细表';
COMMENT ON TABLE reviews IS '商品评价表';

COMMENT ON COLUMN users.city IS '用户所在城市';
COMMENT ON COLUMN products.category IS '产品分类';
COMMENT ON COLUMN products.price IS '产品单价';
COMMENT ON COLUMN orders.total_amount IS '订单总金额';
COMMENT ON COLUMN order_items.quantity IS '购买数量';
COMMENT ON COLUMN order_items.unit_price IS '商品单价';
COMMENT ON COLUMN reviews.rating IS '评分（1-5星）';
COMMENT ON COLUMN reviews.comment IS '评价内容';
