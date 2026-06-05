import json
import os
from werkzeug.security import generate_password_hash


def load_seed_data(app, db):
    """Load seed data from JSON file"""

    seed_file = os.path.join(os.path.dirname(__file__), 'seed_data.json')

    if not os.path.exists(seed_file):
        print("⚠️  seed_data.json not found, skipping seed data loading")
        return

    try:
        with open(seed_file, 'r') as f:
            data = json.load(f)

        with app.app_context():
            # Import models (handle different import patterns)
            from app import User, CompanySetting, PriceListItem, Product, Supplier, Customer

            print("📦 Loading seed data...")

            # 1. Load users
            if 'users' in data:
                for user_data in data['users']:
                    existing_user = User.query.filter_by(username=user_data['username']).first()
                    if not existing_user or user_data.get('force_create', False):
                        if existing_user and user_data.get('force_create', False):
                            # Update existing user
                            existing_user.password = user_data['password']
                            existing_user.role = user_data['role']
                            print(f"🔄 Updated user: {user_data['username']}")
                        else:
                            # Create new user
                            user = User(
                                username=user_data['username'],
                                password=user_data['password'],  # Store as plain text as per your model
                                role=user_data['role']
                            )
                            db.session.add(user)
                            print(f"✅ Created user: {user_data['username']} (role: {user_data['role']})")
                db.session.commit()

            # 2. Load company settings
            if 'company_settings' in data and CompanySetting.query.count() == 0:
                settings = CompanySetting(**data['company_settings'])
                db.session.add(settings)
                db.session.commit()
                print("✅ Created company settings")

            # 3. Load price list items
            if 'price_list_items' in data:
                for item_data in data['price_list_items']:
                    existing = PriceListItem.query.filter_by(item_code=item_data['item_code']).first()
                    if not existing:
                        item = PriceListItem(**item_data)
                        db.session.add(item)
                        print(f"✅ Added price list item: {item_data['item_code']} - {item_data['item_name']}")
                db.session.commit()

            # 4. Load sample products
            if 'sample_products' in data and Product.query.count() == 0:
                for product_data in data['sample_products']:
                    product = Product(**product_data)
                    db.session.add(product)
                    print(f"✅ Added product: {product_data['name']} (SKU: {product_data['sku']})")
                db.session.commit()

            # 5. Load sample suppliers
            if 'sample_suppliers' in data and Supplier.query.count() == 0:
                for supplier_data in data['sample_suppliers']:
                    supplier = Supplier(**supplier_data)
                    db.session.add(supplier)
                    print(f"✅ Added supplier: {supplier_data['name']}")
                db.session.commit()

            # 6. Load sample customers
            if 'sample_customers' in data and Customer.query.count() == 0:
                for customer_data in data['sample_customers']:
                    customer = Customer(**customer_data)
                    db.session.add(customer)
                    print(f"✅ Added customer: {customer_data['name']}")
                db.session.commit()

            print("🎉 Seed data loaded successfully!")

    except Exception as e:
        print(f"❌ Error loading seed data: {e}")
        db.session.rollback()


def ensure_admin_exists(app, db):
    """Ensure at least admin user exists (fallback)"""
    with app.app_context():
        from app import User

        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(username='admin', password='admin123', role='admin')
            db.session.add(admin)
            db.session.commit()
            print("✅ Created default admin user (fallback)")