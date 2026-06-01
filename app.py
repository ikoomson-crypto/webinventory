# app.py - Complete application with admin settings
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from functools import wraps
import json
import os
from werkzeug.utils import secure_filename
from sqlalchemy import func, and_
import pandas as pd
import io
from flask import send_file, make_response
import sqlite3


app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)


# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(50), default='staff')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    telephone = db.Column(db.String(20), nullable=False)
    address = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    telephone = db.Column(db.String(20), nullable=False)
    address = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    sales_description = db.Column(db.Text)
    sku = db.Column(db.String(50), unique=True, nullable=False)
    unit_price = db.Column(db.Float, default=0.0)
    current_quantity_main = db.Column(db.Float, default=0.0)
    current_quantity_sales = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Purchase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    cost_price = db.Column(db.Float, nullable=False)
    total_cost = db.Column(db.Float, nullable=False)
    purchase_date = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)
    reference_no = db.Column(db.String(100), default='')
    product = db.relationship('Product', backref='purchases')
    supplier = db.relationship('Supplier', backref='purchases')


class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    selling_price = db.Column(db.Float, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    sale_date = db.Column(db.DateTime, default=datetime.utcnow)
    source = db.Column(db.String(20), default='sales_store')
    notes = db.Column(db.Text)
    receipt_no = db.Column(db.String(100), default='')
    discount = db.Column(db.Float, default=0)
    product = db.relationship('Product', backref='sales')
    customer = db.relationship('Customer', backref='sales')


class StoreMovement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    from_store = db.Column(db.String(20), nullable=False)
    to_store = db.Column(db.String(20), nullable=False)
    movement_date = db.Column(db.DateTime, default=datetime.utcnow)
    reference = db.Column(db.String(100))
    notes = db.Column(db.Text)
    product = db.relationship('Product', backref='movements')


class CompanySetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(200), default='My Company')
    company_address = db.Column(db.Text, default='')
    company_phone = db.Column(db.String(50), default='')
    company_email = db.Column(db.String(100), default='')
    company_tax_id = db.Column(db.String(100), default='')
    logo_path = db.Column(db.String(200), default='')
    favicon_path = db.Column(db.String(200), default='')
    currency_symbol = db.Column(db.String(10), default='$')
    date_format = db.Column(db.String(20), default='%Y-%m-%d')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SystemLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    action = db.Column(db.String(200))
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='logs')


class Requisition(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    requisition_no = db.Column(db.String(50), unique=True, nullable=False)
    customer = db.Column(db.String(100), nullable=False)
    source_store = db.Column(db.String(20), nullable=False, default='main')
    requested_by = db.Column(db.String(100), nullable=False)
    requested_by_role = db.Column(db.String(50), default='inventory')
    approved_by = db.Column(db.String(100))
    approved_by_role = db.Column(db.String(50))
    purpose = db.Column(db.String(200))
    custom_purpose = db.Column(db.Text)
    reference = db.Column(db.String(100))
    status = db.Column(db.String(20), default='pending')
    requisition_date = db.Column(db.DateTime, default=datetime.utcnow)
    approval_date = db.Column(db.DateTime)
    issue_date = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship('RequisitionItem', backref='requisition', cascade='all, delete-orphan')
    user = db.relationship('User', backref='requisitions')


class RequisitionItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    requisition_id = db.Column(db.Integer, db.ForeignKey('requisition.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    issued_quantity = db.Column(db.Float, default=0)
    notes = db.Column(db.Text)
    product = db.relationship('Product', backref='requisition_items')


# Helper functions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def get_company_settings():
    settings = CompanySetting.query.first()
    if not settings:
        settings = CompanySetting()
        db.session.add(settings)
        db.session.commit()
    return settings


def get_currency_symbol():
    settings = get_company_settings()
    return settings.currency_symbol if settings else '$'


def log_action(user_id, action, details='', ip_address=''):
    log = SystemLog(user_id=user_id, action=action, details=details, ip_address=ip_address)
    db.session.add(log)
    db.session.commit()


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first', 'error')
            return redirect(url_for('login'))
        user = User.query.get(session['user_id'])
        if user.role != 'admin':
            flash('Admin access required', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)

    return decorated_function


# Database migration function
def upgrade_database():
    """Add missing columns to existing tables"""
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()

    # Add sales_description column to product table if it doesn't exist
    try:
        cursor.execute("ALTER TABLE product ADD COLUMN sales_description TEXT DEFAULT ''")
        print("Successfully added sales_description column to product table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("sales_description column already exists")
        else:
            print(f"Error adding sales_description: {e}")

    # Check if requisition table exists and add missing columns
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='requisition'")
    if cursor.fetchone():
        cursor.execute("PRAGMA table_info(requisition)")
        existing_columns = [column[1] for column in cursor.fetchall()]

        columns_to_add = {
            'customer': "ALTER TABLE requisition ADD COLUMN customer VARCHAR(100) DEFAULT ''",
            'source_store': "ALTER TABLE requisition ADD COLUMN source_store VARCHAR(20) DEFAULT 'main'",
            'requested_by_role': "ALTER TABLE requisition ADD COLUMN requested_by_role VARCHAR(50) DEFAULT 'inventory'",
            'approved_by_role': "ALTER TABLE requisition ADD COLUMN approved_by_role VARCHAR(50) DEFAULT ''",
            'custom_purpose': "ALTER TABLE requisition ADD COLUMN custom_purpose TEXT DEFAULT ''",
            'reference': "ALTER TABLE requisition ADD COLUMN reference VARCHAR(100) DEFAULT ''",
            'approval_date': "ALTER TABLE requisition ADD COLUMN approval_date DATETIME",
            'created_by': "ALTER TABLE requisition ADD COLUMN created_by INTEGER REFERENCES user(id)",
            'created_at': "ALTER TABLE requisition ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
        }

        for col_name, alter_sql in columns_to_add.items():
            if col_name not in existing_columns:
                try:
                    cursor.execute(alter_sql)
                    print(f"Added column: {col_name}")
                except sqlite3.OperationalError as e:
                    print(f"Error adding {col_name}: {e}")

    conn.commit()
    conn.close()


# Routes
@app.route('/')
def index():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            log_action(user.id, 'Login', 'User logged in successfully', request.remote_addr)
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')
    return render_template('login.html')


@app.route('/logout')
def logout():
    if 'user_id' in session:
        log_action(session['user_id'], 'Logout', 'User logged out', request.remote_addr)
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    total_products = Product.query.count()
    total_suppliers = Supplier.query.count()
    total_customers = Customer.query.count()
    products = Product.query.all()
    total_stock_value = 0
    for product in products:
        total_stock_value += product.current_quantity_main * product.unit_price
        total_stock_value += product.current_quantity_sales * product.unit_price
    recent_purchases = Purchase.query.order_by(Purchase.purchase_date.desc()).limit(5).all()
    recent_sales = Sale.query.order_by(Sale.sale_date.desc()).limit(5).all()
    recent_movements = StoreMovement.query.order_by(StoreMovement.movement_date.desc()).limit(5).all()
    company_settings = get_company_settings()
    return render_template('dashboard.html',
                           total_products=total_products,
                           total_suppliers=total_suppliers,
                           total_customers=total_customers,
                           total_stock_value=total_stock_value,
                           recent_purchases=recent_purchases,
                           recent_sales=recent_sales,
                           recent_movements=recent_movements,
                           company_settings=company_settings)


# Supplier Management
@app.route('/suppliers')
@login_required
def suppliers():
    suppliers = Supplier.query.all()
    company_settings = get_company_settings()
    return render_template('suppliers.html', suppliers=suppliers, company_settings=company_settings)


@app.route('/add_supplier', methods=['POST'])
@login_required
def add_supplier():
    name = request.form['name']
    telephone = request.form['telephone']
    address = request.form['address']
    supplier = Supplier(name=name, telephone=telephone, address=address)
    db.session.add(supplier)
    db.session.commit()
    log_action(session['user_id'], 'Add Supplier', f'Added supplier: {name}', request.remote_addr)
    flash('Supplier added successfully', 'success')
    return redirect(url_for('suppliers'))


@app.route('/delete_supplier/<int:id>')
@login_required
def delete_supplier(id):
    supplier = Supplier.query.get_or_404(id)
    name = supplier.name
    db.session.delete(supplier)
    db.session.commit()
    log_action(session['user_id'], 'Delete Supplier', f'Deleted supplier: {name}', request.remote_addr)
    flash('Supplier deleted successfully', 'success')
    return redirect(url_for('suppliers'))


# Customer Management
@app.route('/customers')
@login_required
def customers():
    customers = Customer.query.all()
    company_settings = get_company_settings()
    return render_template('customers.html', customers=customers, company_settings=company_settings)


@app.route('/add_customer', methods=['POST'])
@login_required
def add_customer():
    name = request.form['name']
    telephone = request.form['telephone']
    address = request.form['address']
    customer = Customer(name=name, telephone=telephone, address=address)
    db.session.add(customer)
    db.session.commit()
    log_action(session['user_id'], 'Add Customer', f'Added customer: {name}', request.remote_addr)
    flash('Customer added successfully', 'success')
    return redirect(url_for('customers'))


@app.route('/delete_customer/<int:id>')
@login_required
def delete_customer(id):
    customer = Customer.query.get_or_404(id)
    name = customer.name
    db.session.delete(customer)
    db.session.commit()
    log_action(session['user_id'], 'Delete Customer', f'Deleted customer: {name}', request.remote_addr)
    flash('Customer deleted successfully', 'success')
    return redirect(url_for('customers'))


# Product Management
@app.route('/products')
@login_required
def products():
    products = Product.query.all()
    company_settings = get_company_settings()
    return render_template('products.html', products=products, company_settings=company_settings)


@app.route('/add_product', methods=['POST'])
@login_required
def add_product():
    name = request.form['name']
    sku = request.form['sku']
    unit_price = float(request.form['unit_price'])
    description = request.form.get('description', '')
    sales_description = request.form.get('sales_description', '')

    existing = Product.query.filter_by(sku=sku).first()
    if existing:
        flash('SKU already exists', 'error')
        return redirect(url_for('products'))

    product = Product(
        name=name,
        sku=sku,
        unit_price=unit_price,
        description=description,
        sales_description=sales_description,
        current_quantity_main=0,
        current_quantity_sales=0
    )
    db.session.add(product)
    db.session.commit()

    log_action(session['user_id'], 'Add Product', f'Added product: {name} (SKU: {sku})', request.remote_addr)
    flash('Product added successfully', 'success')
    return redirect(url_for('products'))


@app.route('/update_product', methods=['POST'])
@login_required
def update_product():
    product_id = int(request.form['product_id'])
    name = request.form['name']
    unit_price = float(request.form['unit_price'])
    description = request.form.get('description', '')
    sales_description = request.form.get('sales_description', '')

    product = Product.query.get_or_404(product_id)
    product.name = name
    product.unit_price = unit_price
    product.description = description
    product.sales_description = sales_description

    db.session.commit()

    log_action(session['user_id'], 'Update Product', f'Updated product: {product.name} (SKU: {product.sku})',
               request.remote_addr)
    flash('Product updated successfully', 'success')
    return redirect(url_for('products'))


@app.route('/delete_product/<int:id>')
@login_required
def delete_product(id):
    product = Product.query.get_or_404(id)
    name = product.name
    db.session.delete(product)
    db.session.commit()
    log_action(session['user_id'], 'Delete Product', f'Deleted product: {name}', request.remote_addr)
    flash('Product deleted successfully', 'success')
    return redirect(url_for('products'))


# Purchasing
@app.route('/purchases')
@login_required
def purchases():
    purchases = Purchase.query.order_by(Purchase.purchase_date.desc()).all()
    products = Product.query.all()
    suppliers = Supplier.query.all()
    company_settings = get_company_settings()
    return render_template('purchases.html', purchases=purchases, products=products,
                           suppliers=suppliers, company_settings=company_settings)


@app.route('/add_purchase', methods=['POST'])
@login_required
def add_purchase():
    product_id = int(request.form['product_id'])
    supplier_id = int(request.form['supplier_id'])
    quantity = float(request.form['quantity'])
    cost_price = float(request.form['cost_price'])
    notes = request.form.get('notes', '')
    total_cost = quantity * cost_price
    purchase = Purchase(product_id=product_id, supplier_id=supplier_id,
                        quantity=quantity, cost_price=cost_price,
                        total_cost=total_cost, notes=notes)
    product = Product.query.get(product_id)
    product.current_quantity_main += quantity
    db.session.add(purchase)
    db.session.commit()
    log_action(session['user_id'], 'Add Purchase', f'Purchased {quantity} of {product.name}', request.remote_addr)
    flash('Purchase recorded successfully', 'success')
    return redirect(url_for('purchases'))


@app.route('/add_purchase_bulk', methods=['POST'])
@login_required
def add_purchase_bulk():
    supplier_id = int(request.form['supplier_id'])
    purchase_date = datetime.strptime(request.form['purchase_date'], '%Y-%m-%d')
    reference_no = request.form.get('reference_no', '')
    notes = request.form.get('notes', '')
    currency_symbol = get_currency_symbol()
    product_ids = request.form.getlist('product_id[]')
    quantities = request.form.getlist('quantity[]')
    cost_prices = request.form.getlist('cost_price[]')
    total_order_cost = 0
    purchases_created = []
    for i in range(len(product_ids)):
        if product_ids[i] and quantities[i] and cost_prices[i]:
            product_id = int(product_ids[i])
            quantity = float(quantities[i])
            cost_price = float(cost_prices[i])
            total_cost = quantity * cost_price
            total_order_cost += total_cost
            purchase = Purchase(product_id=product_id, supplier_id=supplier_id,
                                quantity=quantity, cost_price=cost_price,
                                total_cost=total_cost, purchase_date=purchase_date,
                                reference_no=reference_no,
                                notes=f"Bulk Order: {reference_no}\n{notes}" if reference_no else notes)
            product = Product.query.get(product_id)
            product.current_quantity_main += quantity
            db.session.add(purchase)
            purchases_created.append(purchase)
    if purchases_created:
        db.session.commit()
        log_action(session['user_id'], 'Bulk Purchase',
                   f'Created purchase order {reference_no} with {len(purchases_created)} items, Total: {currency_symbol}{total_order_cost:.2f}',
                   request.remote_addr)
        flash(f'Purchase order {reference_no} created successfully with {len(purchases_created)} items', 'success')
    else:
        flash('No items were added to the purchase order', 'error')
    return redirect(url_for('purchases'))


# Sales
@app.route('/sales')
@login_required
def sales():
    sales = Sale.query.order_by(Sale.sale_date.desc()).all()
    products = Product.query.all()
    customers = Customer.query.all()
    company_settings = get_company_settings()
    return render_template('sales.html', sales=sales, products=products, customers=customers,
                           company_settings=company_settings)


@app.route('/add_sale', methods=['POST'])
@login_required
def add_sale():
    product_id = int(request.form['product_id'])
    customer_id = int(request.form['customer_id'])
    quantity = float(request.form['quantity'])
    selling_price = float(request.form['selling_price'])
    source = request.form['source']
    notes = request.form.get('notes', '')
    total_amount = quantity * selling_price
    product = Product.query.get(product_id)
    if source == 'main_store' and product.current_quantity_main < quantity:
        flash('Insufficient stock in Main Store', 'error')
        return redirect(url_for('sales'))
    elif source == 'sales_store' and product.current_quantity_sales < quantity:
        flash('Insufficient stock in Sales Store', 'error')
        return redirect(url_for('sales'))
    if source == 'main_store':
        product.current_quantity_main -= quantity
    else:
        product.current_quantity_sales -= quantity
    sale = Sale(product_id=product_id, customer_id=customer_id, quantity=quantity,
                selling_price=selling_price, total_amount=total_amount, source=source, notes=notes)
    db.session.add(sale)
    db.session.commit()
    log_action(session['user_id'], 'Add Sale', f'Sold {quantity} of {product.name} from {source}', request.remote_addr)
    flash('Sale recorded successfully', 'success')
    return redirect(url_for('sales'))


@app.route('/add_sale_bulk', methods=['POST'])
@login_required
def add_sale_bulk():
    customer_id = int(request.form['customer_id'])
    sale_date = datetime.strptime(request.form['sale_date'], '%Y-%m-%d')
    receipt_no = request.form.get('receipt_no', '')
    source = request.form['source']
    discount_percent = float(request.form.get('discount', 0))
    tax_percent = float(request.form.get('tax_rate', 0))
    payment_method = request.form.get('payment_method', 'cash')
    notes = request.form.get('notes', '')
    currency_symbol = get_currency_symbol()
    product_ids = request.form.getlist('product_id[]')
    quantities = request.form.getlist('quantity[]')
    selling_prices = request.form.getlist('selling_price[]')
    total_sale_amount = 0
    sales_created = []
    errors = []
    for i in range(len(product_ids)):
        if product_ids[i] and quantities[i] and selling_prices[i]:
            product_id = int(product_ids[i])
            quantity = float(quantities[i])
            selling_price = float(selling_prices[i])
            item_total = quantity * selling_price
            product = Product.query.get(product_id)
            if source == 'main_store' and product.current_quantity_main < quantity:
                errors.append(
                    f"Insufficient stock for {product.name} in Main Store. Available: {product.current_quantity_main}")
                continue
            elif source == 'sales_store' and product.current_quantity_sales < quantity:
                errors.append(
                    f"Insufficient stock for {product.name} in Sales Store. Available: {product.current_quantity_sales}")
                continue
            if source == 'main_store':
                product.current_quantity_main -= quantity
            else:
                product.current_quantity_sales -= quantity
            total_sale_amount += item_total
            sale = Sale(product_id=product_id, customer_id=customer_id, quantity=quantity,
                        selling_price=selling_price, total_amount=item_total, sale_date=sale_date,
                        source=source, receipt_no=receipt_no, discount=discount_percent,
                        notes=f"Receipt: {receipt_no}\nPayment: {payment_method}\n{notes}")
            db.session.add(sale)
            sales_created.append(sale)
    if sales_created:
        discount_amount = total_sale_amount * (discount_percent / 100)
        after_discount = total_sale_amount - discount_amount
        tax_amount = after_discount * (tax_percent / 100)
        grand_total = after_discount + tax_amount
        for sale in sales_created:
            proportion = sale.total_amount / total_sale_amount if total_sale_amount > 0 else 0
            sale.total_amount = grand_total * proportion
        db.session.commit()
        log_action(session['user_id'], 'Bulk Sale',
                   f'Processed sale {receipt_no} with {len(sales_created)} items, Total: {currency_symbol}{grand_total:.2f}',
                   request.remote_addr)
        flash(
            f'Sale {receipt_no} processed successfully with {len(sales_created)} items! Total: {currency_symbol}{grand_total:.2f}',
            'success')
        if errors:
            flash(f'Warning: {len(errors)} items had issues: {"; ".join(errors[:3])}', 'warning')
    else:
        flash('No items were added to the sale', 'error')
    return redirect(url_for('sales'))


# Store Movements
@app.route('/movements')
@login_required
def movements():
    movements = StoreMovement.query.order_by(StoreMovement.movement_date.desc()).all()
    products = Product.query.all()
    company_settings = get_company_settings()
    return render_template('movements.html', movements=movements, products=products,
                           company_settings=company_settings)


@app.route('/add_movement', methods=['POST'])
@login_required
def add_movement():
    product_id = int(request.form['product_id'])
    quantity = float(request.form['quantity'])
    from_store = request.form['from_store']
    to_store = request.form['to_store']
    notes = request.form.get('notes', '')
    reference = request.form.get('reference', '')
    product = Product.query.get(product_id)
    if from_store == 'main' and product.current_quantity_main < quantity:
        flash('Insufficient stock in Main Store', 'error')
        return redirect(url_for('movements'))
    elif from_store == 'sales' and product.current_quantity_sales < quantity:
        flash('Insufficient stock in Sales Store', 'error')
        return redirect(url_for('movements'))
    if from_store == 'main':
        product.current_quantity_main -= quantity
    else:
        product.current_quantity_sales -= quantity
    if to_store == 'main':
        product.current_quantity_main += quantity
    else:
        product.current_quantity_sales += quantity
    movement = StoreMovement(product_id=product_id, quantity=quantity,
                             from_store=from_store, to_store=to_store,
                             reference=reference, notes=notes)
    db.session.add(movement)
    db.session.commit()
    log_action(session['user_id'], 'Store Movement',
               f'Moved {quantity} of {product.name} from {from_store} to {to_store}', request.remote_addr)
    flash('Stock movement recorded successfully', 'success')
    return redirect(url_for('movements'))


# Price List Management
@app.route('/price_list')
@login_required
def price_list():
    products = Product.query.order_by(Product.name).all()
    company_settings = get_company_settings()
    return render_template('price_list.html', products=products, company_settings=company_settings)


@app.route('/update_price_list', methods=['POST'])
@login_required
def update_price_list():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        updated_count = 0
        for product_id, new_price in data.items():
            product = Product.query.get(int(product_id))
            if product:
                product.unit_price = float(new_price)
                updated_count += 1
        db.session.commit()
        log_action(session['user_id'], 'Update Price List', f'Updated prices for {updated_count} products',
                   request.remote_addr)
        return jsonify({'success': True, 'updated': updated_count})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/export_price_list')
@login_required
def export_price_list():
    products = Product.query.order_by(Product.name).all()
    data = []
    for product in products:
        data.append({
            'SKU': product.sku,
            'Product Name': product.name,
            'Description': product.description or '',
            'Sales Description': product.sales_description or '',
            'Current Price': product.unit_price,
            'Main Store Stock': product.current_quantity_main,
            'Sales Store Stock': product.current_quantity_sales,
            'Total Stock': product.current_quantity_main + product.current_quantity_sales,
            'Stock Value': (product.current_quantity_main + product.current_quantity_sales) * product.unit_price
        })
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Price List', index=False)
        worksheet = writer.sheets['Price List']
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name=f'price_list_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx')


@app.route('/add_movement_bulk', methods=['POST'])
@login_required
def add_movement_bulk():
    """Handle bulk store movements with multiple items"""
    movement_date = datetime.strptime(request.form['movement_date'], '%Y-%m-%d')
    reference = request.form.get('reference', '')
    notes = request.form.get('notes', '')

    product_ids = request.form.getlist('product_id[]')
    quantities = request.form.getlist('quantity[]')
    from_stores = request.form.getlist('from_store[]')
    to_stores = request.form.getlist('to_store[]')

    movements_created = []
    errors = []

    for i in range(len(product_ids)):
        if product_ids[i] and quantities[i] and from_stores[i] and to_stores[i]:
            product_id = int(product_ids[i])
            quantity = float(quantities[i])
            from_store = from_stores[i]
            to_store = to_stores[i]

            product = Product.query.get(product_id)

            # Check stock in source store
            if from_store == 'main' and product.current_quantity_main < quantity:
                errors.append(
                    f"Insufficient stock in Main Store for {product.name}. Available: {product.current_quantity_main}")
                continue
            elif from_store == 'sales' and product.current_quantity_sales < quantity:
                errors.append(
                    f"Insufficient stock in Sales Store for {product.name}. Available: {product.current_quantity_sales}")
                continue

            # Check if source and destination are the same
            if from_store == to_store:
                errors.append(f"Source and destination stores cannot be the same for {product.name}")
                continue

            # Update quantities
            if from_store == 'main':
                product.current_quantity_main -= quantity
            else:
                product.current_quantity_sales -= quantity

            if to_store == 'main':
                product.current_quantity_main += quantity
            else:
                product.current_quantity_sales += quantity

            # Create movement record
            movement = StoreMovement(
                product_id=product_id,
                quantity=quantity,
                from_store=from_store,
                to_store=to_store,
                movement_date=movement_date,
                reference=reference,
                notes=f"Bulk Transfer: {reference}\n{notes}" if reference else notes
            )

            db.session.add(movement)
            movements_created.append(movement)

    if movements_created:
        db.session.commit()
        log_action(session['user_id'], 'Bulk Store Movement',
                   f'Created transfer with {len(movements_created)} items, Reference: {reference}',
                   request.remote_addr)
        flash(f'Successfully transferred {len(movements_created)} items!', 'success')
        if errors:
            flash(f'Warning: {len(errors)} items had issues: {"; ".join(errors[:3])}', 'warning')
    else:
        flash('No items were added to the transfer', 'error')

    return redirect(url_for('movements'))


@app.route('/reset_price_list', methods=['POST'])
@login_required
@admin_required
def reset_price_list():
    try:
        products = Product.query.all()
        for product in products:
            purchases = Purchase.query.filter_by(product_id=product.id).all()
            if purchases:
                avg_price = sum(p.cost_price for p in purchases) / len(purchases)
                product.unit_price = avg_price
            else:
                product.unit_price = 0
        db.session.commit()
        log_action(session['user_id'], 'Reset Price List', 'Reset all product prices', request.remote_addr)
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# Reports
@app.route('/reports')
@login_required
def reports():
    company_settings = get_company_settings()
    return render_template('reports.html', company_settings=company_settings)


@app.route('/sales_report')
@login_required
def sales_report():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    query = Sale.query
    if start_date:
        query = query.filter(Sale.sale_date >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(Sale.sale_date <= datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1))
    sales = query.order_by(Sale.sale_date.desc()).all()
    total_sales_amount = sum(sale.total_amount for sale in sales)
    total_items_sold = sum(sale.quantity for sale in sales)
    company_settings = get_company_settings()
    return render_template('sales_report.html', sales=sales, total_sales_amount=total_sales_amount,
                           total_items_sold=total_items_sold, start_date=start_date, end_date=end_date,
                           company_settings=company_settings)


@app.route('/purchases_report')
@login_required
def purchases_report():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    query = Purchase.query
    if start_date:
        query = query.filter(Purchase.purchase_date >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(Purchase.purchase_date <= datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1))
    purchases = query.order_by(Purchase.purchase_date.desc()).all()
    total_purchase_cost = sum(purchase.total_cost for purchase in purchases)
    total_items_purchased = sum(purchase.quantity for purchase in purchases)
    company_settings = get_company_settings()
    return render_template('purchases_report.html', purchases=purchases,
                           total_purchase_cost=total_purchase_cost, total_items_purchased=total_items_purchased,
                           start_date=start_date, end_date=end_date, company_settings=company_settings)


@app.route('/movements_report')
@login_required
def movements_report():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    query = StoreMovement.query
    if start_date:
        query = query.filter(StoreMovement.movement_date >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(StoreMovement.movement_date <= datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1))
    movements = query.order_by(StoreMovement.movement_date.desc()).all()
    main_to_sales = sum(m.quantity for m in movements if m.from_store == 'main' and m.to_store == 'sales')
    sales_to_main = sum(m.quantity for m in movements if m.from_store == 'sales' and m.to_store == 'main')
    company_settings = get_company_settings()
    return render_template('movements_report.html', movements=movements,
                           main_to_sales=main_to_sales, sales_to_main=sales_to_main,
                           start_date=start_date, end_date=end_date, company_settings=company_settings)


@app.route('/costing_report')
@login_required
def costing_report():
    products = Product.query.all()
    costing_data = []
    for product in products:
        purchases = Purchase.query.filter_by(product_id=product.id).order_by(Purchase.purchase_date).all()
        if purchases:
            total_cost = sum(p.total_cost for p in purchases)
            total_quantity = sum(p.quantity for p in purchases)
            weighted_avg_cost = total_cost / total_quantity if total_quantity > 0 else 0
            fifo_cost = purchases[0].cost_price if purchases else 0
            remaining_quantity = product.current_quantity_main + product.current_quantity_sales
            fifo_value = 0
            remaining = remaining_quantity
            for purchase in purchases:
                if remaining <= 0:
                    break
                qty_to_use = min(purchase.quantity, remaining)
                fifo_value += qty_to_use * purchase.cost_price
                remaining -= qty_to_use
            weighted_value = remaining_quantity * weighted_avg_cost
        else:
            weighted_avg_cost = 0
            fifo_cost = 0
            fifo_value = 0
            weighted_value = 0
        costing_data.append({
            'product': product,
            'fifo_cost': fifo_cost,
            'weighted_avg_cost': weighted_avg_cost,
            'fifo_value': fifo_value,
            'weighted_value': weighted_value,
            'total_quantity': product.current_quantity_main + product.current_quantity_sales
        })
    company_settings = get_company_settings()
    return render_template('costing_report.html', costing_data=costing_data, company_settings=company_settings)


@app.route('/stock_summary_report')
@login_required
def stock_summary_report():
    store = request.args.get('store', 'main')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    stock_data = []
    totals = {'opening': 0, 'purchases': 0, 'sales': 0, 'movements_in': 0, 'movements_out': 0, 'closing': 0,
              'closing_value': 0}
    if start_date_str and end_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)
        products = Product.query.all()
        for product in products:
            if store == 'all':
                purchases_before = db.session.query(func.sum(Purchase.quantity)).filter(
                    Purchase.product_id == product.id, Purchase.purchase_date < start_date).scalar() or 0
                sales_before_main = db.session.query(func.sum(Sale.quantity)).filter(
                    Sale.product_id == product.id, Sale.source == 'main_store',
                    Sale.sale_date < start_date).scalar() or 0
                sales_before_sales = db.session.query(func.sum(Sale.quantity)).filter(
                    Sale.product_id == product.id, Sale.source == 'sales_store',
                    Sale.sale_date < start_date).scalar() or 0
                sales_before = sales_before_main + sales_before_sales
                opening = purchases_before - sales_before
                purchases = db.session.query(func.sum(Purchase.quantity)).filter(
                    Purchase.product_id == product.id, Purchase.purchase_date >= start_date,
                    Purchase.purchase_date < end_date).scalar() or 0
                sales_main = db.session.query(func.sum(Sale.quantity)).filter(
                    Sale.product_id == product.id, Sale.source == 'main_store', Sale.sale_date >= start_date,
                    Sale.sale_date < end_date).scalar() or 0
                sales_sales = db.session.query(func.sum(Sale.quantity)).filter(
                    Sale.product_id == product.id, Sale.source == 'sales_store', Sale.sale_date >= start_date,
                    Sale.sale_date < end_date).scalar() or 0
                sales = sales_main + sales_sales
                movements_in = 0
                movements_out = 0
                closing = opening + purchases - sales
                closing_value = closing * product.unit_price
            elif store == 'main':
                purchases_before = db.session.query(func.sum(Purchase.quantity)).filter(
                    Purchase.product_id == product.id, Purchase.purchase_date < start_date).scalar() or 0
                sales_before = db.session.query(func.sum(Sale.quantity)).filter(
                    Sale.product_id == product.id, Sale.source == 'main_store',
                    Sale.sale_date < start_date).scalar() or 0
                movements_out_before = db.session.query(func.sum(StoreMovement.quantity)).filter(
                    StoreMovement.product_id == product.id, StoreMovement.from_store == 'main',
                    StoreMovement.movement_date < start_date).scalar() or 0
                movements_in_before = db.session.query(func.sum(StoreMovement.quantity)).filter(
                    StoreMovement.product_id == product.id, StoreMovement.to_store == 'main',
                    StoreMovement.movement_date < start_date).scalar() or 0
                opening = purchases_before - sales_before - movements_out_before + movements_in_before
                purchases = db.session.query(func.sum(Purchase.quantity)).filter(
                    Purchase.product_id == product.id, Purchase.purchase_date >= start_date,
                    Purchase.purchase_date < end_date).scalar() or 0
                sales = db.session.query(func.sum(Sale.quantity)).filter(
                    Sale.product_id == product.id, Sale.source == 'main_store', Sale.sale_date >= start_date,
                    Sale.sale_date < end_date).scalar() or 0
                movements_in = db.session.query(func.sum(StoreMovement.quantity)).filter(
                    StoreMovement.product_id == product.id, StoreMovement.to_store == 'main',
                    StoreMovement.movement_date >= start_date, StoreMovement.movement_date < end_date).scalar() or 0
                movements_out = db.session.query(func.sum(StoreMovement.quantity)).filter(
                    StoreMovement.product_id == product.id, StoreMovement.from_store == 'main',
                    StoreMovement.movement_date >= start_date, StoreMovement.movement_date < end_date).scalar() or 0
                closing = opening + purchases + movements_in - sales - movements_out
                closing_value = closing * product.unit_price
            else:
                movements_in_before = db.session.query(func.sum(StoreMovement.quantity)).filter(
                    StoreMovement.product_id == product.id, StoreMovement.to_store == 'sales',
                    StoreMovement.movement_date < start_date).scalar() or 0
                sales_before = db.session.query(func.sum(Sale.quantity)).filter(
                    Sale.product_id == product.id, Sale.source == 'sales_store',
                    Sale.sale_date < start_date).scalar() or 0
                movements_out_before = db.session.query(func.sum(StoreMovement.quantity)).filter(
                    StoreMovement.product_id == product.id, StoreMovement.from_store == 'sales',
                    StoreMovement.movement_date < start_date).scalar() or 0
                opening = movements_in_before - sales_before - movements_out_before
                purchases = 0
                sales = db.session.query(func.sum(Sale.quantity)).filter(
                    Sale.product_id == product.id, Sale.source == 'sales_store', Sale.sale_date >= start_date,
                    Sale.sale_date < end_date).scalar() or 0
                movements_in = db.session.query(func.sum(StoreMovement.quantity)).filter(
                    StoreMovement.product_id == product.id, StoreMovement.to_store == 'sales',
                    StoreMovement.movement_date >= start_date, StoreMovement.movement_date < end_date).scalar() or 0
                movements_out = db.session.query(func.sum(StoreMovement.quantity)).filter(
                    StoreMovement.product_id == product.id, StoreMovement.from_store == 'sales',
                    StoreMovement.movement_date >= start_date, StoreMovement.movement_date < end_date).scalar() or 0
                closing = opening + movements_in - sales - movements_out
                closing_value = closing * product.unit_price
            if opening != 0 or purchases != 0 or sales != 0 or movements_in != 0 or movements_out != 0 or closing != 0:
                stock_data.append({
                    'sku': product.sku, 'name': product.name, 'opening': opening, 'purchases': purchases,
                    'sales': sales, 'movements_in': movements_in, 'movements_out': movements_out,
                    'closing': closing, 'unit_price': product.unit_price, 'closing_value': closing_value
                })
                totals['opening'] += opening
                totals['purchases'] += purchases
                totals['sales'] += sales
                totals['movements_in'] += movements_in
                totals['movements_out'] += movements_out
                totals['closing'] += closing
                totals['closing_value'] += closing_value
        stock_data.sort(key=lambda x: x['name'])
    company_settings = get_company_settings()
    return render_template('stock_summary_report.html', stock_data=stock_data, totals=totals,
                           total_value=totals['closing_value'], selected_store=store,
                           start_date=start_date_str, end_date=end_date_str, company_settings=company_settings)


# Admin Settings Routes
@app.route('/admin/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_settings():
    settings = get_company_settings()
    if request.method == 'POST':
        settings.company_name = request.form.get('company_name', 'My Company')
        settings.company_address = request.form.get('company_address', '')
        settings.company_phone = request.form.get('company_phone', '')
        settings.company_email = request.form.get('company_email', '')
        settings.company_tax_id = request.form.get('company_tax_id', '')
        settings.currency_symbol = request.form.get('currency_symbol', '$')
        db.session.commit()
        log_action(session['user_id'], 'Update Settings', 'Updated company settings', request.remote_addr)
        flash('Company settings updated successfully', 'success')
        return redirect(url_for('admin_settings'))
    return render_template('admin_settings.html', settings=settings)


@app.route('/admin/upload_logo', methods=['POST'])
@login_required
@admin_required
def upload_logo():
    if 'logo' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('admin_settings'))
    file = request.files['logo']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('admin_settings'))
    if file and allowed_file(file.filename):
        filename = secure_filename(
            f"logo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{file.filename.rsplit('.', 1)[1].lower()}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        settings = get_company_settings()
        if settings.logo_path:
            old_logo_path = os.path.join(app.config['UPLOAD_FOLDER'], settings.logo_path)
            if os.path.exists(old_logo_path):
                os.remove(old_logo_path)
        settings.logo_path = filename
        db.session.commit()
        log_action(session['user_id'], 'Upload Logo', f'Uploaded logo: {filename}', request.remote_addr)
        flash('Logo uploaded successfully', 'success')
    else:
        flash('Invalid file type. Allowed: png, jpg, jpeg, gif, webp', 'error')
    return redirect(url_for('admin_settings'))


@app.route('/admin/remove_logo')
@login_required
@admin_required
def remove_logo():
    settings = get_company_settings()
    if settings.logo_path:
        logo_path = os.path.join(app.config['UPLOAD_FOLDER'], settings.logo_path)
        if os.path.exists(logo_path):
            os.remove(logo_path)
        settings.logo_path = ''
        db.session.commit()
        log_action(session['user_id'], 'Remove Logo', 'Removed company logo', request.remote_addr)
        flash('Logo removed successfully', 'success')
    return redirect(url_for('admin_settings'))


@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    users = User.query.all()
    return render_template('admin_users.html', users=users)


@app.route('/admin/add_user', methods=['POST'])
@login_required
@admin_required
def add_user():
    username = request.form['username']
    password = request.form['password']
    role = request.form['role']
    existing = User.query.filter_by(username=username).first()
    if existing:
        flash('Username already exists', 'error')
        return redirect(url_for('admin_users'))
    user = User(username=username, password=password, role=role)
    db.session.add(user)
    db.session.commit()
    log_action(session['user_id'], 'Add User', f'Added user: {username} with role {role}', request.remote_addr)
    flash('User added successfully', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/delete_user/<int:id>')
@login_required
@admin_required
def delete_user(id):
    user = User.query.get_or_404(id)
    if user.id == session['user_id']:
        flash('Cannot delete your own account', 'error')
        return redirect(url_for('admin_users'))
    username = user.username
    db.session.delete(user)
    db.session.commit()
    log_action(session['user_id'], 'Delete User', f'Deleted user: {username}', request.remote_addr)
    flash('User deleted successfully', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/change_password', methods=['POST'])
@login_required
@admin_required
def change_password():
    user_id = request.form.get('user_id')
    new_password = request.form['new_password']
    user = User.query.get_or_404(user_id)
    user.password = new_password
    db.session.commit()
    log_action(session['user_id'], 'Change Password', f'Changed password for user: {user.username}',
               request.remote_addr)
    flash('Password changed successfully', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/system_logs')
@login_required
@admin_required
def system_logs():
    logs = SystemLog.query.order_by(SystemLog.timestamp.desc()).limit(200).all()
    return render_template('system_logs.html', logs=logs)


@app.route('/admin/backup')
@login_required
@admin_required
def backup_database():
    import shutil
    backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    shutil.copy('inventory.db', backup_name)
    flash(f'Database backed up as {backup_name}', 'success')
    return redirect(url_for('admin_settings'))


# Export Functions
@app.route('/export_suppliers')
@login_required
def export_suppliers():
    suppliers = Supplier.query.all()
    data = [{'ID': s.id, 'Name': s.name, 'Telephone': s.telephone, 'Address': s.address,
             'Created Date': s.created_at.strftime('%Y-%m-%d %H:%M:%S') if s.created_at else ''} for s in suppliers]
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Suppliers', index=False)
        worksheet = writer.sheets['Suppliers']
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True,
                     download_name=f'suppliers_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx')


@app.route('/export_customers')
@login_required
def export_customers():
    customers = Customer.query.all()
    data = [{'ID': c.id, 'Name': c.name, 'Telephone': c.telephone, 'Address': c.address,
             'Created Date': c.created_at.strftime('%Y-%m-%d %H:%M:%S') if c.created_at else ''} for c in customers]
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Customers', index=False)
        worksheet = writer.sheets['Customers']
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True,
                     download_name=f'customers_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx')


@app.route('/export_products')
@login_required
def export_products():
    products = Product.query.all()
    data = []
    for p in products:
        data.append({
            'ID': p.id, 'SKU': p.sku, 'Name': p.name, 'Description': p.description or '',
            'Sales Description': p.sales_description or '',
            'Unit Price': p.unit_price, 'Main Store Quantity': p.current_quantity_main,
            'Sales Store Quantity': p.current_quantity_sales,
            'Total Quantity': p.current_quantity_main + p.current_quantity_sales,
            'Total Value': (p.current_quantity_main + p.current_quantity_sales) * p.unit_price,
            'Created Date': p.created_at.strftime('%Y-%m-%d %H:%M:%S') if p.created_at else ''
        })
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Products', index=False)
        worksheet = writer.sheets['Products']
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True,
                     download_name=f'products_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx')


@app.route('/export_sales')
@login_required
def export_sales():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    query = Sale.query
    if start_date:
        query = query.filter(Sale.sale_date >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(Sale.sale_date <= datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1))
    sales = query.order_by(Sale.sale_date.desc()).all()
    data = []
    for sale in sales:
        data.append({
            'ID': sale.id,
            'Date': sale.sale_date.strftime('%Y-%m-%d %H:%M:%S'),
            'Receipt No': sale.receipt_no or '',
            'Product Name': sale.product.name,
            'Sales Description': sale.product.sales_description or sale.product.name,  # Add this
            'Product SKU': sale.product.sku,
            'Customer': sale.customer.name,
            'Customer Phone': sale.customer.telephone,
            'Quantity': sale.quantity,
            'Unit Price': sale.selling_price,
            'Subtotal': sale.quantity * sale.selling_price,
            'Discount (%)': sale.discount or 0,
            'Total Amount': sale.total_amount,
            'Store Source': 'Main Store' if sale.source == 'main_store' else 'Sales Store',
            'Notes': sale.notes or ''
        })
    # ... rest of the export code

@app.route('/export_purchases')
@login_required
def export_purchases():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    query = Purchase.query
    if start_date:
        query = query.filter(Purchase.purchase_date >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(Purchase.purchase_date <= datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1))
    purchases = query.order_by(Purchase.purchase_date.desc()).all()
    data = []
    for purchase in purchases:
        data.append({
            'ID': purchase.id, 'Date': purchase.purchase_date.strftime('%Y-%m-%d %H:%M:%S'),
            'Reference No': purchase.reference_no or '',
            'Product': purchase.product.name, 'Product SKU': purchase.product.sku, 'Supplier': purchase.supplier.name,
            'Supplier Phone': purchase.supplier.telephone, 'Quantity': purchase.quantity,
            'Cost Price': purchase.cost_price,
            'Total Cost': purchase.total_cost, 'Notes': purchase.notes or ''
        })
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Purchases', index=False)
        if data:
            currency_symbol = get_currency_symbol()
            summary_data = {
                'Metric': ['Total Purchases', 'Total Items Purchased', 'Average Purchase Value',
                           'Number of Transactions'],
                'Value': [f"{currency_symbol}{sum(p.total_cost for p in purchases):.2f}",
                          sum(p.quantity for p in purchases),
                          f"{currency_symbol}{(sum(p.total_cost for p in purchases) / len(purchases)):.2f}" if purchases else '0',
                          len(purchases)]
            }
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
        worksheet = writer.sheets['Purchases']
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True,
                     download_name=f'purchases_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx')


@app.route('/export_movements')
@login_required
def export_movements():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    query = StoreMovement.query
    if start_date:
        query = query.filter(StoreMovement.movement_date >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(StoreMovement.movement_date <= datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1))
    movements = query.order_by(StoreMovement.movement_date.desc()).all()
    data = []
    for movement in movements:
        data.append({
            'Date': movement.movement_date.strftime('%Y-%m-%d %H:%M:%S'), 'Product': movement.product.name,
            'Product SKU': movement.product.sku, 'Quantity': movement.quantity,
            'From Store': 'Main Store' if movement.from_store == 'main' else 'Sales Store',
            'To Store': 'Main Store' if movement.to_store == 'main' else 'Sales Store',
            'Reference': movement.reference or '', 'Notes': movement.notes or ''
        })
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Store Movements', index=False)
        if data:
            main_to_sales = sum(m.quantity for m in movements if m.from_store == 'main' and m.to_store == 'sales')
            sales_to_main = sum(m.quantity for m in movements if m.from_store == 'sales' and m.to_store == 'main')
            summary_data = {'Metric': ['Main → Sales Store', 'Sales → Main Store', 'Net Movement', 'Total Movements'],
                            'Value': [main_to_sales, sales_to_main, main_to_sales - sales_to_main, len(movements)]}
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
        worksheet = writer.sheets['Store Movements']
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True,
                     download_name=f'movements_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx')


# Import Functions
@app.route('/import_suppliers', methods=['POST'])
@login_required
@admin_required
def import_suppliers():
    if 'file' not in request.files:
        flash('No file uploaded', 'error')
        return redirect(url_for('suppliers'))
    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('suppliers'))
    if not file.filename.endswith(('.xlsx', '.xls')):
        flash('Please upload an Excel file (.xlsx or .xls)', 'error')
        return redirect(url_for('suppliers'))
    try:
        df = pd.read_excel(file)
        imported_count = 0
        error_count = 0
        for index, row in df.iterrows():
            try:
                supplier = Supplier(name=row['Name'],
                                    telephone=str(row['Telephone']) if pd.notna(row.get('Telephone')) else '',
                                    address=row['Address'] if pd.notna(row.get('Address')) else '')
                db.session.add(supplier)
                imported_count += 1
            except Exception as e:
                error_count += 1
        db.session.commit()
        log_action(session['user_id'], 'Import Suppliers', f'Imported {imported_count} suppliers, {error_count} errors',
                   request.remote_addr)
        flash(f'Successfully imported {imported_count} suppliers. {error_count} errors.', 'success')
    except Exception as e:
        flash(f'Error importing file: {str(e)}', 'error')
    return redirect(url_for('suppliers'))


@app.route('/import_customers', methods=['POST'])
@login_required
@admin_required
def import_customers():
    if 'file' not in request.files:
        flash('No file uploaded', 'error')
        return redirect(url_for('customers'))
    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('customers'))
    if not file.filename.endswith(('.xlsx', '.xls')):
        flash('Please upload an Excel file (.xlsx or .xls)', 'error')
        return redirect(url_for('customers'))
    try:
        df = pd.read_excel(file)
        imported_count = 0
        error_count = 0
        for index, row in df.iterrows():
            try:
                customer = Customer(name=row['Name'],
                                    telephone=str(row['Telephone']) if pd.notna(row.get('Telephone')) else '',
                                    address=row['Address'] if pd.notna(row.get('Address')) else '')
                db.session.add(customer)
                imported_count += 1
            except Exception as e:
                error_count += 1
        db.session.commit()
        log_action(session['user_id'], 'Import Customers', f'Imported {imported_count} customers, {error_count} errors',
                   request.remote_addr)
        flash(f'Successfully imported {imported_count} customers. {error_count} errors.', 'success')
    except Exception as e:
        flash(f'Error importing file: {str(e)}', 'error')
    return redirect(url_for('customers'))


@app.route('/import_products', methods=['POST'])
@login_required
@admin_required
def import_products():
    if 'file' not in request.files:
        flash('No file uploaded', 'error')
        return redirect(url_for('products'))
    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('products'))
    if not file.filename.endswith(('.xlsx', '.xls')):
        flash('Please upload an Excel file (.xlsx or .xls)', 'error')
        return redirect(url_for('products'))
    try:
        df = pd.read_excel(file)
        imported_count = 0
        error_count = 0
        skipped_count = 0
        for index, row in df.iterrows():
            try:
                existing = Product.query.filter_by(sku=row['SKU']).first()
                if existing:
                    skipped_count += 1
                    continue
                product = Product(
                    name=row['Name'],
                    sku=row['SKU'],
                    description=row.get('Description', '') if pd.notna(row.get('Description')) else '',
                    sales_description=row.get('Sales Description', '') if pd.notna(
                        row.get('Sales Description')) else '',
                    unit_price=float(row['Unit Price']) if pd.notna(row.get('Unit Price')) else 0,
                    current_quantity_main=float(row.get('Main Store Quantity', 0)) if pd.notna(
                        row.get('Main Store Quantity')) else 0,
                    current_quantity_sales=float(row.get('Sales Store Quantity', 0)) if pd.notna(
                        row.get('Sales Store Quantity')) else 0
                )
                db.session.add(product)
                imported_count += 1
            except Exception as e:
                error_count += 1
        db.session.commit()
        log_action(session['user_id'], 'Import Products',
                   f'Imported {imported_count} products, {error_count} errors, {skipped_count} skipped',
                   request.remote_addr)
        flash(
            f'Successfully imported {imported_count} products. {error_count} errors. {skipped_count} skipped (duplicate SKUs).',
            'success')
    except Exception as e:
        flash(f'Error importing file: {str(e)}', 'error')
    return redirect(url_for('products'))


@app.route('/import_purchases', methods=['POST'])
@login_required
@admin_required
def import_purchases():
    if 'file' not in request.files:
        flash('No file uploaded', 'error')
        return redirect(url_for('purchases'))
    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('purchases'))
    if not file.filename.endswith(('.xlsx', '.xls')):
        flash('Please upload an Excel file (.xlsx or .xls)', 'error')
        return redirect(url_for('purchases'))
    try:
        df = pd.read_excel(file)
        required_columns = ['Product SKU', 'Supplier Name', 'Quantity', 'Cost Price']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            flash(f'Missing required columns: {", ".join(missing_columns)}', 'error')
            return redirect(url_for('purchases'))
        imported_count = 0
        error_count = 0
        errors = []
        for index, row in df.iterrows():
            try:
                product = Product.query.filter_by(sku=str(row['Product SKU']).strip()).first()
                if not product:
                    errors.append(f"Row {index + 2}: Product SKU '{row['Product SKU']}' not found")
                    error_count += 1
                    continue
                supplier = Supplier.query.filter_by(name=str(row['Supplier Name']).strip()).first()
                if not supplier:
                    errors.append(f"Row {index + 2}: Supplier '{row['Supplier Name']}' not found")
                    error_count += 1
                    continue
                quantity = float(row['Quantity'])
                cost_price = float(row['Cost Price'])
                total_cost = quantity * cost_price
                purchase_date = datetime.now()
                if 'Purchase Date' in df.columns and pd.notna(row['Purchase Date']):
                    purchase_date = pd.to_datetime(row['Purchase Date'])
                reference_no = str(row['Reference No']) if 'Reference No' in df.columns and pd.notna(
                    row.get('Reference No')) else ''
                notes = str(row['Notes']) if 'Notes' in df.columns and pd.notna(row.get('Notes')) else ''
                purchase = Purchase(product_id=product.id, supplier_id=supplier.id, quantity=quantity,
                                    cost_price=cost_price,
                                    total_cost=total_cost, purchase_date=purchase_date, reference_no=reference_no,
                                    notes=f"Bulk Import: {notes}" if notes else "Bulk Import")
                product.current_quantity_main += quantity
                db.session.add(purchase)
                imported_count += 1
            except Exception as e:
                errors.append(f"Row {index + 2}: {str(e)}")
                error_count += 1
        db.session.commit()
        log_action(session['user_id'], 'Bulk Import Purchases',
                   f'Imported {imported_count} purchases, {error_count} errors', request.remote_addr)
        if errors:
            flash(
                f'Successfully imported {imported_count} purchases. {error_count} errors.\nFirst few errors: {"; ".join(errors[:3])}',
                'warning')
        else:
            flash(f'Successfully imported {imported_count} purchases!', 'success')
    except Exception as e:
        flash(f'Error importing file: {str(e)}', 'error')
    return redirect(url_for('purchases'))


@app.route('/import_sales', methods=['POST'])
@login_required
@admin_required
def import_sales():
    if 'file' not in request.files:
        flash('No file uploaded', 'error')
        return redirect(url_for('sales'))
    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('sales'))
    if not file.filename.endswith(('.xlsx', '.xls')):
        flash('Please upload an Excel file (.xlsx or .xls)', 'error')
        return redirect(url_for('sales'))
    try:
        df = pd.read_excel(file)
        required_columns = ['Product SKU', 'Customer Name', 'Quantity', 'Selling Price', 'Store Source']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            flash(f'Missing required columns: {", ".join(missing_columns)}', 'error')
            return redirect(url_for('sales'))
        imported_count = 0
        error_count = 0
        errors = []
        for index, row in df.iterrows():
            try:
                product = Product.query.filter_by(sku=str(row['Product SKU']).strip()).first()
                if not product:
                    errors.append(f"Row {index + 2}: Product SKU '{row['Product SKU']}' not found")
                    error_count += 1
                    continue
                customer = Customer.query.filter_by(name=str(row['Customer Name']).strip()).first()
                if not customer:
                    errors.append(f"Row {index + 2}: Customer '{row['Customer Name']}' not found")
                    error_count += 1
                    continue
                quantity = float(row['Quantity'])
                selling_price = float(row['Selling Price'])
                source = str(row['Store Source']).strip().lower()
                if source not in ['main_store', 'sales_store']:
                    if source in ['main', 'Main', 'MAIN']:
                        source = 'main_store'
                    elif source in ['sales', 'Sales', 'SALES']:
                        source = 'sales_store'
                    else:
                        errors.append(
                            f"Row {index + 2}: Store Source must be 'main_store' or 'sales_store'. Got '{source}'")
                        error_count += 1
                        continue
                if source == 'main_store' and product.current_quantity_main < quantity:
                    errors.append(
                        f"Row {index + 2}: Insufficient stock for {product.name} in Main Store. Available: {product.current_quantity_main}")
                    error_count += 1
                    continue
                elif source == 'sales_store' and product.current_quantity_sales < quantity:
                    errors.append(
                        f"Row {index + 2}: Insufficient stock for {product.name} in Sales Store. Available: {product.current_quantity_sales}")
                    error_count += 1
                    continue
                total_amount = quantity * selling_price
                sale_date = datetime.now()
                if 'Sale Date' in df.columns and pd.notna(row['Sale Date']):
                    sale_date = pd.to_datetime(row['Sale Date'])
                receipt_no = str(row['Receipt No']) if 'Receipt No' in df.columns and pd.notna(
                    row.get('Receipt No')) else ''
                discount = float(row['Discount (%)']) if 'Discount (%)' in df.columns and pd.notna(
                    row.get('Discount (%)')) else 0
                discounted_amount = total_amount * (1 - discount / 100)
                notes = str(row['Notes']) if 'Notes' in df.columns and pd.notna(row.get('Notes')) else ''
                if source == 'main_store':
                    product.current_quantity_main -= quantity
                else:
                    product.current_quantity_sales -= quantity
                sale = Sale(product_id=product.id, customer_id=customer.id, quantity=quantity,
                            selling_price=selling_price,
                            total_amount=discounted_amount, sale_date=sale_date, source=source, receipt_no=receipt_no,
                            discount=discount, notes=f"Bulk Import: {notes}" if notes else "Bulk Import")
                db.session.add(sale)
                imported_count += 1
            except Exception as e:
                errors.append(f"Row {index + 2}: {str(e)}")
                error_count += 1
        db.session.commit()
        log_action(session['user_id'], 'Bulk Import Sales', f'Imported {imported_count} sales, {error_count} errors',
                   request.remote_addr)
        if errors:
            flash(
                f'Successfully imported {imported_count} sales. {error_count} errors.\nFirst few errors: {"; ".join(errors[:3])}',
                'warning')
        else:
            flash(f'Successfully imported {imported_count} sales!', 'success')
    except Exception as e:
        flash(f'Error importing file: {str(e)}', 'error')
    return redirect(url_for('sales'))


# Download Templates
@app.route('/download_purchase_template')
@login_required
@admin_required
def download_purchase_template():
    template_data = {'Product SKU': ['SKU001', 'SKU002', 'SKU003'],
                     'Supplier Name': ['ABC Suppliers', 'XYZ Distributors', 'ABC Suppliers'],
                     'Quantity': [100, 50, 75], 'Cost Price': [10.50, 25.00, 15.75],
                     'Purchase Date': ['2024-01-15', '2024-01-16', '2024-01-17'],
                     'Reference No': ['PO-001', 'PO-002', 'PO-003'],
                     'Notes': ['First order', 'Regular stock', 'Urgent order']}
    df = pd.DataFrame(template_data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Purchase Template', index=False)
        instructions = pd.DataFrame({'Column': ['Product SKU', 'Supplier Name', 'Quantity', 'Cost Price',
                                                'Purchase Date', 'Reference No', 'Notes'],
                                     'Required': ['Yes', 'Yes', 'Yes', 'Yes', 'No', 'No', 'No'],
                                     'Description': ['Must match existing product SKU',
                                                     'Must match existing supplier name', 'Numeric value',
                                                     'Numeric value (cost per unit)', 'Date format: YYYY-MM-DD',
                                                     'Optional reference/invoice number', 'Optional notes']})
        instructions.to_excel(writer, sheet_name='Instructions', index=False)
        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name='purchase_import_template.xlsx')


@app.route('/download_sales_template')
@login_required
@admin_required
def download_sales_template():
    """Download Excel template for bulk sales import"""
    template_data = {
        'Product SKU': ['SKU001', 'SKU002', 'SKU003'],
        'Customer Name': ['John Doe', 'Jane Smith', 'Bob Johnson'],
        'Quantity': [5, 3, 2],
        'Selling Price': [15.00, 35.00, 25.00],
        'Store Source': ['main_store', 'sales_store', 'main_store'],
        'Sale Date': ['2024-01-15', '2024-01-16', '2024-01-17'],
        'Receipt No': ['INV-001', 'INV-002', 'INV-003'],
        'Discount (%)': [0, 10, 5],
        'Notes': ['Cash sale', 'Credit sale', 'Discounted']
    }

    df = pd.DataFrame(template_data)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Sales Template', index=False)

        instructions = pd.DataFrame({
            'Column': ['Product SKU', 'Customer Name', 'Quantity', 'Selling Price', 'Store Source', 'Sale Date',
                       'Receipt No', 'Discount (%)', 'Notes'],
            'Required': ['Yes', 'Yes', 'Yes', 'Yes', 'Yes', 'No', 'No', 'No', 'No'],
            'Description': [
                'Must match existing product SKU',
                'Must match existing customer name',
                'Numeric value',
                'Numeric value (selling price per unit)',
                'Must be "main_store" or "sales_store"',
                'Date format: YYYY-MM-DD',
                'Optional receipt/invoice number',
                'Discount percentage (0-100)',
                'Optional notes'
            ]
        })
        instructions.to_excel(writer, sheet_name='Instructions', index=False)

        valid_values = pd.DataFrame({
            'Store Source Options': ['main_store', 'sales_store'],
            'Description': ['Main Store/Warehouse', 'Sales Store/Retail']
        })
        valid_values.to_excel(writer, sheet_name='Valid Values', index=False)

        # Auto-adjust column widths
        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width

    output.seek(0)

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='sales_import_template.xlsx'
    )

# Requisitions Management
@app.route('/requisitions')
@login_required
def requisitions():
    user = User.query.get(session['user_id'])
    if user.role == 'admin':
        requisitions = Requisition.query.order_by(Requisition.requisition_date.desc()).all()
    elif user.role == 'accountant':
        requisitions = Requisition.query.filter(Requisition.status.in_(['pending', 'approved', 'issued'])).order_by(
            Requisition.requisition_date.desc()).all()
    else:
        requisitions = Requisition.query.filter_by(created_by=session['user_id']).order_by(
            Requisition.requisition_date.desc()).all()
    company_settings = get_company_settings()
    return render_template('requisitions.html', requisitions=requisitions, company_settings=company_settings,
                           user_role=user.role)


@app.route('/new_requisition', methods=['GET', 'POST'])
@login_required
def new_requisition():
    if request.method == 'POST':
        requisition_no = f"REQ-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        requisition_date = datetime.strptime(request.form['requisition_date'], '%Y-%m-%d')
        source_store = request.form['source_store']
        requested_by = request.form['requested_by']
        purpose = request.form.get('purpose', '')
        custom_purpose = request.form.get('custom_purpose', '') if purpose == 'other' else ''
        reference = request.form.get('reference', '')
        notes = request.form.get('notes', '')
        user = User.query.get(session['user_id'])
        requested_by_role = user.role

        requisition = Requisition(
            requisition_no=requisition_no,
            requisition_date=requisition_date,
            source_store=source_store,
            requested_by=requested_by,
            requested_by_role=requested_by_role,
            purpose=purpose if purpose != 'other' else 'other',
            custom_purpose=custom_purpose if purpose == 'other' else '',
            reference=reference,
            notes=notes,
            status='pending',
            created_by=session['user_id']
        )
        db.session.add(requisition)
        db.session.flush()

        # Add items
        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')

        for i in range(len(product_ids)):
            if product_ids[i] and quantities[i]:
                product_id = int(product_ids[i])
                quantity = float(quantities[i])
                item = RequisitionItem(
                    requisition_id=requisition.id,
                    product_id=product_id,
                    quantity=quantity,
                    notes=request.form.get(f'item_notes_{i}', '')
                )
                db.session.add(item)

        db.session.commit()

        log_action(session['user_id'], 'Create Requisition',
                   f'Created requisition {requisition_no} for {requested_by}',
                   request.remote_addr)

        flash(f'Requisition {requisition_no} created successfully!', 'success')
        return redirect(url_for('view_requisition', id=requisition.id))

    # GET request - display the form
    products = Product.query.order_by(Product.name).all()
    customers = Customer.query.order_by(Customer.name).all()
    company_settings = get_company_settings()
    return render_template('new_requisition.html',
                           products=products,
                           customers=customers,
                           company_settings=company_settings)
@app.route('/requisition/<int:id>')
@login_required
def view_requisition(id):
    requisition = Requisition.query.get_or_404(id)
    user = User.query.get(session['user_id'])
    company_settings = get_company_settings()
    return render_template('view_requisition.html', requisition=requisition, company_settings=company_settings,
                           user_role=user.role)


@app.route('/approve_requisition/<int:id>', methods=['POST'])
@login_required
def approve_requisition(id):
    requisition = Requisition.query.get_or_404(id)
    user = User.query.get(session['user_id'])
    if user.role != 'accountant' and user.role != 'admin':
        flash('Only accountants can approve requisitions', 'error')
        return redirect(url_for('view_requisition', id=id))
    if requisition.status != 'pending':
        flash('This requisition has already been processed', 'error')
        return redirect(url_for('view_requisition', id=id))
    requisition.status = 'approved'
    requisition.approved_by = session['username']
    requisition.approved_by_role = user.role
    requisition.approval_date = datetime.utcnow()
    db.session.commit()
    log_action(session['user_id'], 'Approve Requisition', f'Approved requisition {requisition.requisition_no}',
               request.remote_addr)
    flash(f'Requisition {requisition.requisition_no} has been approved!', 'success')
    return redirect(url_for('view_requisition', id=id))


@app.route('/reject_requisition/<int:id>', methods=['POST'])
@login_required
def reject_requisition(id):
    requisition = Requisition.query.get_or_404(id)
    user = User.query.get(session['user_id'])
    if user.role != 'accountant' and user.role != 'admin':
        flash('Only accountants can reject requisitions', 'error')
        return redirect(url_for('view_requisition', id=id))
    if requisition.status != 'pending':
        flash('This requisition has already been processed', 'error')
        return redirect(url_for('view_requisition', id=id))
    reason = request.form.get('rejection_reason', 'No reason provided')
    requisition.status = 'rejected'
    requisition.approved_by = session['username']
    requisition.approved_by_role = user.role
    requisition.notes = f"Rejected: {reason}\n{requisition.notes or ''}"
    db.session.commit()
    log_action(session['user_id'], 'Reject Requisition', f'Rejected requisition {requisition.requisition_no}',
               request.remote_addr)
    flash(f'Requisition {requisition.requisition_no} has been rejected', 'warning')
    return redirect(url_for('view_requisition', id=id))


@app.route('/issue_requisition/<int:id>', methods=['POST'])
@login_required
def issue_requisition(id):
    requisition = Requisition.query.get_or_404(id)
    if requisition.status != 'approved':
        flash('Requisition must be approved before issuing', 'error')
        return redirect(url_for('view_requisition', id=id))
    for item in requisition.items:
        product = Product.query.get(item.product_id)
        if requisition.source_store == 'main':
            if product.current_quantity_main < item.quantity:
                flash(
                    f'Insufficient stock in Main Store for {product.name}. Available: {product.current_quantity_main}',
                    'error')
                return redirect(url_for('view_requisition', id=id))
            product.current_quantity_main -= item.quantity
        else:
            if product.current_quantity_sales < item.quantity:
                flash(
                    f'Insufficient stock in Sales Store for {product.name}. Available: {product.current_quantity_sales}',
                    'error')
                return redirect(url_for('view_requisition', id=id))
            product.current_quantity_sales -= item.quantity
        item.issued_quantity = item.quantity
    requisition.status = 'issued'
    requisition.issue_date = datetime.utcnow()
    requisition.approved_by = requisition.approved_by or session['username']
    db.session.commit()
    log_action(session['user_id'], 'Issue Requisition',
               f'Issued requisition {requisition.requisition_no} from {requisition.source_store} store',
               request.remote_addr)
    flash(f'Requisition {requisition.requisition_no} has been issued!', 'success')
    return redirect(url_for('view_requisition', id=id))


@app.route('/cancel_requisition/<int:id>')
@login_required
def cancel_requisition(id):
    requisition = Requisition.query.get_or_404(id)
    user = User.query.get(session['user_id'])
    if requisition.created_by != session['user_id'] and user.role != 'admin':
        flash('You can only cancel your own requisitions', 'error')
        return redirect(url_for('view_requisition', id=id))
    if requisition.status != 'pending':
        flash('Only pending requisitions can be cancelled', 'error')
        return redirect(url_for('view_requisition', id=id))
    requisition.status = 'cancelled'
    db.session.commit()
    log_action(session['user_id'], 'Cancel Requisition', f'Cancelled requisition {requisition.requisition_no}',
               request.remote_addr)
    flash(f'Requisition {requisition.requisition_no} has been cancelled', 'success')
    return redirect(url_for('requisitions'))


@app.route('/delete_requisition/<int:id>')
@login_required
@admin_required
def delete_requisition(id):
    requisition = Requisition.query.get_or_404(id)
    requisition_no = requisition.requisition_no
    db.session.delete(requisition)
    db.session.commit()
    log_action(session['user_id'], 'Delete Requisition', f'Deleted requisition {requisition_no}', request.remote_addr)
    flash(f'Requisition {requisition_no} has been deleted', 'success')
    return redirect(url_for('requisitions'))


@app.route('/bulk_delete_products', methods=['POST'])
@login_required
@admin_required
def bulk_delete_products():
    """Delete multiple products at once"""
    try:
        data = request.get_json()
        product_ids = data.get('product_ids', [])

        if not product_ids:
            return jsonify({'success': False, 'error': 'No products selected'}), 400

        deleted_count = 0
        error_count = 0
        errors = []

        for product_id in product_ids:
            try:
                product = Product.query.get(int(product_id))
                if product:
                    product_name = product.name

                    # Check if product has any related records (optional warning)
                    purchase_count = Purchase.query.filter_by(product_id=product.id).count()
                    sale_count = Sale.query.filter_by(product_id=product.id).count()
                    movement_count = StoreMovement.query.filter_by(product_id=product.id).count()
                    requisition_count = RequisitionItem.query.filter_by(product_id=product.id).count()

                    if purchase_count > 0 or sale_count > 0 or movement_count > 0 or requisition_count > 0:
                        errors.append(
                            f"{product_name}: Has {purchase_count} purchases, {sale_count} sales, {movement_count} movements")

                    # Delete the product (cascade will handle related records)
                    db.session.delete(product)
                    deleted_count += 1
                    log_action(session['user_id'], 'Bulk Delete Product',
                               f'Deleted product: {product_name} (ID: {product_id})', request.remote_addr)
            except Exception as e:
                error_count += 1
                errors.append(f"Product ID {product_id}: {str(e)}")

        db.session.commit()

        message = f'Successfully deleted {deleted_count} product(s).'
        if errors:
            message += f' {len(errors)} warning(s): {"; ".join(errors[:3])}'

        return jsonify({
            'success': True,
            'deleted_count': deleted_count,
            'error_count': error_count,
            'errors': errors[:5]  # Return first 5 errors
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/print_requisition/<int:id>')
@login_required
def print_requisition(id):
    requisition = Requisition.query.get_or_404(id)
    company_settings = get_company_settings()
    return render_template('print_requisition.html', requisition=requisition, company_settings=company_settings,
                           now=datetime.now())


# Serve uploaded files
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# Context processors
@app.context_processor
def inject_company_settings():
    settings = get_company_settings()
    logo_url = url_for('uploaded_file', filename=settings.logo_path) if settings.logo_path else None
    return {'company_settings': settings, 'logo_url': logo_url,
            'currency_symbol': settings.currency_symbol if settings else '$'}


@app.context_processor
def inject_now():
    return {'now': datetime.now()}


@app.context_processor
def inject_filters():
    return {'format_number': lambda x: f"{x:,.2f}" if isinstance(x, float) else f"{x:,}",
            'format_currency': lambda x, s=None: f"{s or '$'}{x:,.2f}" if x else f"{s or '$'}0.00"}


# Template filters
@app.template_filter('format_number')
def format_number(value):
    if value is None:
        return '0'
    try:
        if isinstance(value, float):
            return f"{value:,.2f}"
        else:
            return f"{value:,}"
    except (ValueError, TypeError):
        return str(value)


@app.template_filter('format_currency')
def format_currency(value, symbol='$'):
    if value is None:
        return f"{symbol}0.00"
    try:
        return f"{symbol}{value:,.2f}"
    except (ValueError, TypeError):
        return f"{symbol}0.00"


# Initialize database
def init_db():
    with app.app_context():
        db.create_all()
        upgrade_database()

        # Create default users
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', password='admin123', role='admin')
            db.session.add(admin)
            print("Default admin created: username='admin', password='admin123'")

        if not User.query.filter_by(username='accountant').first():
            accountant = User(username='accountant', password='accountant123', role='accountant')
            db.session.add(accountant)
            print("Default accountant created: username='accountant', password='accountant123'")

        if not User.query.filter_by(username='inventory').first():
            inventory = User(username='inventory', password='inventory123', role='inventory')
            db.session.add(inventory)
            print("Default inventory user created: username='inventory', password='inventory123'")

        db.session.commit()

        # Create default company settings
        if not CompanySetting.query.first():
            settings = CompanySetting(company_name='My Inventory System',
                                      company_address='123 Business Street\nCity, State 12345',
                                      company_phone='+1 (555) 123-4567', company_email='info@mycompany.com',
                                      currency_symbol='$')
            db.session.add(settings)
            db.session.commit()
            print("Default company settings created")


if __name__ == '__main__':
    init_db()
    app.run(debug=True)