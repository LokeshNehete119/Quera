CREATE TABLE products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    stock INT NOT NULL DEFAULT 0
);

CREATE TABLE orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL,
    quantity INT NOT NULL,
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

INSERT INTO products (name, price, stock) VALUES 
('Laptop', 999.99, 50),
('Smartphone', 499.99, 150),
('Headphones', 79.99, 200);

INSERT INTO orders (product_id, quantity) VALUES 
(1, 2),
(2, 5),
(3, 10);
