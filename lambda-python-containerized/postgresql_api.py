import os
import logging
import boto3
from datetime import datetime
import uuid
import random
import psycopg2
from psycopg2.extras import RealDictCursor
from lumigo_tracer import add_execution_tag, lumigo_tracer

# Configure logging
logger = logging.getLogger()



class PostgreSQLDAL:
    """
    Data Access Layer for PostgreSQL RDS operations.
    This class wraps PostgreSQL operations with proper error handling and logging.
    """
    
    def __init__(self, table_name="users"):
        self.table_name = table_name
        self.database_name = os.environ.get('RDS_DATABASE_NAME', 'lumigo_test')
        self.host = os.environ.get('RDS_HOST', 'localhost')
        self.port = int(os.environ.get('RDS_PORT', '5432'))
        self.username = os.environ.get('RDS_USERNAME', 'lumigo_admin')
        self.password = os.environ.get('RDS_PASSWORD', 'LumigoTest123!')
        
        self.connection_available = False
        self.connection = None
        
        # Try to get RDS endpoint from environment or AWS
        try:
            # Always try to get RDS endpoint from AWS first
            rds_client = boto3.client('rds')
            response = rds_client.describe_db_instances(
                DBInstanceIdentifier='lumigo-test-postgres'
            )
            if response['DBInstances']:
                instance = response['DBInstances'][0]
                if instance['DBInstanceStatus'] == 'available':
                    self.host = instance['Endpoint']['Address']
                    self.connection_available = True
                    logger.info(f"✅ RDS PostgreSQL endpoint found: {self.host}")
                else:
                    logger.warning(f"⚠️  RDS instance status: {instance['DBInstanceStatus']}")
                    # Fall back to environment variables if RDS not available
                    if self.host and self.host != 'localhost':
                        self.connection_available = True
            else:
                logger.warning("⚠️  RDS instance not found, using simulation mode")
        except Exception as e:
            logger.warning(f"⚠️  Could not get RDS endpoint: {str(e)}, using simulation mode")
            # Fall back to environment variables if RDS discovery fails
            if self.host and self.host != 'localhost':
                self.connection_available = True
    
    def get_connection(self):
        """Get a database connection"""
        if not self.connection_available:
            logger.warning("⚠️  Connection not available")
            return None
            
        try:
            if self.connection is None or self.connection.closed:
                logger.info(f"🔌 Connecting to PostgreSQL: {self.host}:{self.port}/{self.database_name}")
                self.connection = psycopg2.connect(
                    host=self.host,
                    port=self.port,
                    database=self.database_name,
                    user=self.username,
                    password=self.password,
                    connect_timeout=5,  # 5 second timeout
                    options='-c statement_timeout=3000'  # 3 second query timeout
                )
                logger.info("✅ Database connection established")
            return self.connection
        except Exception as e:
            logger.error(f"❌ Database connection failed: {str(e)}")
            return None
    
    def ensure_table_exists(self):
        """
        Ensure the users, products, and orders tables exist in the database.
        Creates tables if they don't exist.
        """
        try:
            if not self.connection_available:
                logger.info("📋 Simulating table creation (no real connection)")
                return True
            
            conn = self.get_connection()
            if not conn:
                logger.warning("⚠️  No database connection available, using simulation")
                return True
            
            cursor = conn.cursor()
            
            # Create users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id VARCHAR(255) PRIMARY KEY,
                    username VARCHAR(255) NOT NULL,
                    email VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status VARCHAR(50) DEFAULT 'active'
                )
            """)
            
            # Create products table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id VARCHAR(255) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    price DECIMAL(10,2) NOT NULL,
                    category VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status VARCHAR(50) DEFAULT 'active'
                )
            """)
            
            # Create orders table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id VARCHAR(255) PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    total_amount DECIMAL(10,2) NOT NULL,
                    status VARCHAR(50) DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            
            conn.commit()
            cursor.close()
            
            logger.info(f"✅ Tables 'users', 'products', 'orders' are ready")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to ensure tables exist: {str(e)}")
            return False
    
    @lumigo_tracer()
    def create_user(self, user_data):
        """
        Create a new user in the database.
        
        Args:
            user_data (dict): User data to insert
            
        Returns:
            dict: Response with operation details
        """
        try:
            user_id = user_data.get('id', str(uuid.uuid4()))
            username = user_data.get('username', f'user_{random.randint(1000, 9999)}')
            email = user_data.get('email', f'user_{random.randint(1000, 9999)}@example.com')
            
            if not self.connection_available:
                # Simulate INSERT operation
                logger.info(f"📝 Simulating INSERT into {self.table_name}")
                return {
                    'affected_rows': 1,
                    'user_id': user_id,
                    'status': 'created',
                    'operation': 'INSERT'
                }
            
            conn = self.get_connection()
            if not conn:
                logger.warning("⚠️  No database connection available, using simulation")
                return {
                    'affected_rows': 1,
                    'user_id': user_id,
                    'status': 'created',
                    'operation': 'INSERT'
                }
            
            # Add Lumigo execution tags for PostgreSQL operation
            add_execution_tag("postgresql_operation", "INSERT")
            add_execution_tag("postgresql_table", "users")
            add_execution_tag("postgresql_user_id", user_id)
            
            logger.info(f"📝 Executing real INSERT into users table: {user_id}")
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (id, username, email, status)
                VALUES (%s, %s, %s, %s)
            """, (user_id, username, email, 'active'))
            
            conn.commit()
            cursor.close()
            
            logger.info(f"✅ Created user: {user_id}")
            return {
                'affected_rows': 1,
                'user_id': user_id,
                'status': 'created',
                'operation': 'INSERT'
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to create user: {str(e)}")
            raise
    
    def insert_product(self, product_data):
        """
        Insert a new product into the products table.
        
        Args:
            product_data (dict): Product data to insert
            
        Returns:
            dict: Response with operation details
        """
        try:
            product_id = product_data.get('id', str(uuid.uuid4()))
            name = product_data.get('name', f'Product {random.randint(100, 999)}')
            price = product_data.get('price', round(random.uniform(10.0, 1000.0), 2))
            category = product_data.get('category', random.choice(['Electronics', 'Clothing', 'Books', 'Home']))
            
            if not self.connection_available:
                # Simulate INSERT operation
                logger.info(f"📝 Simulating INSERT into products table")
                return {
                    'affected_rows': 1,
                    'product_id': product_id,
                    'status': 'created',
                    'operation': 'INSERT_PRODUCT'
                }
            
            conn = self.get_connection()
            if not conn:
                logger.warning("⚠️  No database connection available, using simulation")
                return {
                    'affected_rows': 1,
                    'product_id': product_id,
                    'status': 'created',
                    'operation': 'INSERT_PRODUCT'
                }
            
            # Add Lumigo execution tags for PostgreSQL operation
            add_execution_tag("postgresql_operation", "INSERT")
            add_execution_tag("postgresql_table", "products")
            add_execution_tag("postgresql_product_id", product_id)
            
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO products (id, name, price, category, status)
                VALUES (%s, %s, %s, %s, %s)
            """, (product_id, name, price, category, 'active'))
            
            conn.commit()
            cursor.close()
            
            logger.info(f"✅ Created product: {product_id}")
            return {
                'affected_rows': 1,
                'product_id': product_id,
                'status': 'created',
                'operation': 'INSERT_PRODUCT'
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to insert product: {str(e)}")
            raise
    
    def insert_order(self, order_data):
        """
        Insert a new order into the orders table.
        
        Args:
            order_data (dict): Order data to insert
            
        Returns:
            dict: Response with operation details
        """
        try:
            order_id = order_data.get('id', str(uuid.uuid4()))
            user_id = order_data.get('user_id', str(uuid.uuid4()))
            total_amount = order_data.get('total_amount', round(random.uniform(50.0, 500.0), 2))
            
            if not self.connection_available:
                # Simulate INSERT operation
                logger.info(f"📝 Simulating INSERT into orders table")
                return {
                    'affected_rows': 1,
                    'order_id': order_id,
                    'status': 'created',
                    'operation': 'INSERT_ORDER'
                }
            
            conn = self.get_connection()
            if not conn:
                logger.warning("⚠️  No database connection available, using simulation")
                return {
                    'affected_rows': 1,
                    'order_id': order_id,
                    'status': 'created',
                    'operation': 'INSERT_ORDER'
                }
            
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO orders (id, user_id, total_amount, status)
                VALUES (%s, %s, %s, %s)
            """, (order_id, user_id, total_amount, 'pending'))
            
            conn.commit()
            cursor.close()
            
            logger.info(f"✅ Created order: {order_id}")
            return {
                'affected_rows': 1,
                'order_id': order_id,
                'status': 'created',
                'operation': 'INSERT_ORDER'
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to insert order: {str(e)}")
            raise
    
    @lumigo_tracer()
    def read_user(self, user_id):
        """
        Read a user from the database.
        
        Args:
            user_id (str): User ID to read
            
        Returns:
            dict: User data and operation details
        """
        try:
            if not self.connection_available:
                # Simulate SELECT operation
                logger.info(f"📖 Simulating SELECT from {self.table_name}")
                return {
                    'user_found': True,
                    'user_data': {
                        'id': user_id,
                        'username': f'user_{random.randint(1000, 9999)}',
                        'email': f'user_{random.randint(1000, 9999)}@example.com',
                        'created_at': datetime.utcnow().isoformat(),
                        'status': 'active'
                    },
                    'query_time': random.uniform(0.01, 0.05),
                    'operation': 'SELECT'
                }
            
            conn = self.get_connection()
            if not conn:
                logger.warning("⚠️  No database connection available, using simulation")
                return {
                    'user_found': True,
                    'user_data': {
                        'id': user_id,
                        'username': f'user_{random.randint(1000, 9999)}',
                        'email': f'user_{random.randint(1000, 9999)}@example.com',
                        'created_at': datetime.utcnow().isoformat(),
                        'status': 'active'
                    },
                    'query_time': random.uniform(0.01, 0.05),
                    'operation': 'SELECT'
                }
            
            # Add Lumigo execution tags for PostgreSQL operation
            add_execution_tag("postgresql_operation", "SELECT")
            add_execution_tag("postgresql_table", "users")
            add_execution_tag("postgresql_user_id", user_id)
            
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT id, username, email, created_at, status
                FROM users WHERE id = %s
            """, (user_id,))
            
            result = cursor.fetchone()
            cursor.close()
            
            if result:
                user_data = dict(result)
                user_data['created_at'] = user_data['created_at'].isoformat() if user_data['created_at'] else None
                logger.info(f"✅ Found user: {user_id}")
                return {
                    'user_found': True,
                    'user_data': user_data,
                    'query_time': random.uniform(0.01, 0.05),
                    'operation': 'SELECT'
                }
            else:
                logger.warning(f"⚠️  User not found: {user_id}")
                return {
                    'user_found': False,
                    'user_data': None,
                    'query_time': random.uniform(0.01, 0.05),
                    'operation': 'SELECT'
                }
            
        except Exception as e:
            logger.error(f"❌ Failed to read user: {str(e)}")
            raise
    
    @lumigo_tracer()
    def update_user(self, user_id, updates):
        """
        Update a user in the database.
        
        Args:
            user_id (str): User ID to update
            updates (dict): Fields to update
            
        Returns:
            dict: Response with operation details
        """
        try:
            if not self.connection_available:
                # Simulate UPDATE operation
                logger.info(f"📝 Simulating UPDATE in {self.table_name}")
                return {
                    'affected_rows': 1,
                    'updated_fields': list(updates.keys()),
                    'status': 'updated',
                    'operation': 'UPDATE'
                }
            
            conn = self.get_connection()
            if not conn:
                logger.warning("⚠️  No database connection available, using simulation")
                return {
                    'affected_rows': 1,
                    'updated_fields': list(updates.keys()),
                    'status': 'updated',
                    'operation': 'UPDATE'
                }
            
            # Add Lumigo execution tags for PostgreSQL operation
            add_execution_tag("postgresql_operation", "UPDATE")
            add_execution_tag("postgresql_table", "users")
            add_execution_tag("postgresql_user_id", user_id)
            add_execution_tag("postgresql_updated_fields", ",".join(updates.keys()))
            
            # Build dynamic UPDATE query
            set_clauses = []
            values = []
            for field, value in updates.items():
                if field in ['username', 'email', 'status']:
                    set_clauses.append(f"{field} = %s")
                    values.append(value)
            
            if not set_clauses:
                logger.warning("⚠️  No valid fields to update")
                return {
                    'affected_rows': 0,
                    'updated_fields': [],
                    'status': 'no_changes',
                    'operation': 'UPDATE'
                }
            
            set_clauses.append("updated_at = CURRENT_TIMESTAMP")
            values.append(user_id)
            
            query = f"UPDATE users SET {', '.join(set_clauses)} WHERE id = %s"
            cursor = conn.cursor()
            cursor.execute(query, values)
            
            affected_rows = cursor.rowcount
            conn.commit()
            cursor.close()
            
            logger.info(f"✅ Updated user: {user_id} ({affected_rows} rows affected)")
            return {
                'affected_rows': affected_rows,
                'updated_fields': list(updates.keys()),
                'status': 'updated',
                'operation': 'UPDATE'
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to update user: {str(e)}")
            raise
    
    def update_product(self, product_id, updates):
        """
        Update a product in the database.
        
        Args:
            product_id (str): Product ID to update
            updates (dict): Fields to update
            
        Returns:
            dict: Response with operation details
        """
        try:
            if not self.connection_available:
                # Simulate UPDATE operation
                logger.info(f"📝 Simulating UPDATE in products table")
                return {
                    'affected_rows': 1,
                    'updated_fields': list(updates.keys()),
                    'status': 'updated',
                    'operation': 'UPDATE_PRODUCT'
                }
            
            conn = self.get_connection()
            if not conn:
                logger.warning("⚠️  No database connection available, using simulation")
                return {
                    'affected_rows': 1,
                    'updated_fields': list(updates.keys()),
                    'status': 'updated',
                    'operation': 'UPDATE_PRODUCT'
                }
            
            cursor = conn.cursor()
            
            # Build dynamic UPDATE query
            set_clauses = []
            values = []
            for field, value in updates.items():
                if field in ['name', 'price', 'category', 'status']:
                    set_clauses.append(f"{field} = %s")
                    values.append(value)
            
            if not set_clauses:
                logger.warning("⚠️  No valid fields to update")
                return {
                    'affected_rows': 0,
                    'updated_fields': [],
                    'status': 'no_changes',
                    'operation': 'UPDATE_PRODUCT'
                }
            
            set_clauses.append("updated_at = CURRENT_TIMESTAMP")
            values.append(product_id)
            
            query = f"UPDATE products SET {', '.join(set_clauses)} WHERE id = %s"
            cursor.execute(query, values)
            
            affected_rows = cursor.rowcount
            conn.commit()
            cursor.close()
            
            logger.info(f"✅ Updated product: {product_id} ({affected_rows} rows affected)")
            return {
                'affected_rows': affected_rows,
                'updated_fields': list(updates.keys()),
                'status': 'updated',
                'operation': 'UPDATE_PRODUCT'
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to update product: {str(e)}")
            raise
    
    def update_order_status(self, order_id, new_status):
        """
        Update an order status in the database.
        
        Args:
            order_id (str): Order ID to update
            new_status (str): New status value
            
        Returns:
            dict: Response with operation details
        """
        try:
            if not self.connection_available:
                # Simulate UPDATE operation
                logger.info(f"📝 Simulating UPDATE in orders table")
                return {
                    'affected_rows': 1,
                    'updated_fields': ['status'],
                    'status': 'updated',
                    'operation': 'UPDATE_ORDER_STATUS'
                }
            
            conn = self.get_connection()
            if not conn:
                logger.warning("⚠️  No database connection available, using simulation")
                return {
                    'affected_rows': 1,
                    'updated_fields': ['status'],
                    'status': 'updated',
                    'operation': 'UPDATE_ORDER_STATUS'
                }
            
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE orders SET status = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (new_status, order_id))
            
            affected_rows = cursor.rowcount
            conn.commit()
            cursor.close()
            
            logger.info(f"✅ Updated order status: {order_id} -> {new_status} ({affected_rows} rows affected)")
            return {
                'affected_rows': affected_rows,
                'updated_fields': ['status'],
                'status': 'updated',
                'operation': 'UPDATE_ORDER_STATUS'
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to update order status: {str(e)}")
            raise
    
    @lumigo_tracer()
    def delete_user(self, user_id):
        """
        Delete a user from the database.
        
        Args:
            user_id (str): User ID to delete
            
        Returns:
            dict: Response with operation details
        """
        try:
            if not self.connection_available:
                # Simulate DELETE operation
                logger.info(f"🗑️  Simulating DELETE from {self.table_name}")
                return {
                    'affected_rows': 1,
                    'deleted_user_id': user_id,
                    'status': 'deleted',
                    'operation': 'DELETE'
                }
            
            conn = self.get_connection()
            if not conn:
                logger.warning("⚠️  No database connection available, using simulation")
                return {
                    'affected_rows': 1,
                    'deleted_user_id': user_id,
                    'status': 'deleted',
                    'operation': 'DELETE'
                }
            
            # Add Lumigo execution tags for PostgreSQL operation
            add_execution_tag("postgresql_operation", "DELETE")
            add_execution_tag("postgresql_table", "users")
            add_execution_tag("postgresql_user_id", user_id)
            
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
            
            affected_rows = cursor.rowcount
            conn.commit()
            cursor.close()
            
            logger.info(f"✅ Deleted user: {user_id} ({affected_rows} rows affected)")
            return {
                'affected_rows': affected_rows,
                'deleted_user_id': user_id,
                'status': 'deleted',
                'operation': 'DELETE'
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to delete user: {str(e)}")
            raise
    
    def delete_product(self, product_id):
        """
        Delete a product from the database.
        
        Args:
            product_id (str): Product ID to delete
            
        Returns:
            dict: Response with operation details
        """
        try:
            if not self.connection_available:
                # Simulate DELETE operation
                logger.info(f"🗑️  Simulating DELETE from products table")
                return {
                    'affected_rows': 1,
                    'deleted_product_id': product_id,
                    'status': 'deleted',
                    'operation': 'DELETE_PRODUCT'
                }
            
            conn = self.get_connection()
            if not conn:
                logger.warning("⚠️  No database connection available, using simulation")
                return {
                    'affected_rows': 1,
                    'deleted_product_id': product_id,
                    'status': 'deleted',
                    'operation': 'DELETE_PRODUCT'
                }
            
            cursor = conn.cursor()
            cursor.execute("DELETE FROM products WHERE id = %s", (product_id,))
            
            affected_rows = cursor.rowcount
            conn.commit()
            cursor.close()
            
            logger.info(f"✅ Deleted product: {product_id} ({affected_rows} rows affected)")
            return {
                'affected_rows': affected_rows,
                'deleted_product_id': product_id,
                'status': 'deleted',
                'operation': 'DELETE_PRODUCT'
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to delete product: {str(e)}")
            raise
    
    def delete_order(self, order_id):
        """
        Delete an order from the database.
        
        Args:
            order_id (str): Order ID to delete
            
        Returns:
            dict: Response with operation details
        """
        try:
            if not self.connection_available:
                # Simulate DELETE operation
                logger.info(f"🗑️  Simulating DELETE from orders table")
                return {
                    'affected_rows': 1,
                    'deleted_order_id': order_id,
                    'status': 'deleted',
                    'operation': 'DELETE_ORDER'
                }
            
            conn = self.get_connection()
            if not conn:
                logger.warning("⚠️  No database connection available, using simulation")
                return {
                    'affected_rows': 1,
                    'deleted_order_id': order_id,
                    'status': 'deleted',
                    'operation': 'DELETE_ORDER'
                }
            
            cursor = conn.cursor()
            cursor.execute("DELETE FROM orders WHERE id = %s", (order_id,))
            
            affected_rows = cursor.rowcount
            conn.commit()
            cursor.close()
            
            logger.info(f"✅ Deleted order: {order_id} ({affected_rows} rows affected)")
            return {
                'affected_rows': affected_rows,
                'deleted_order_id': order_id,
                'status': 'deleted',
                'operation': 'DELETE_ORDER'
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to delete order: {str(e)}")
            raise 