import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'lpg-gaspinas-secret-2024-!@#$')

    # Neon PostgreSQL database
    NEON_DB_URL = 'postgresql://neondb_owner:npg_h5JTl0OzuZYU@ep-winter-lake-anho9gpz-pooler.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require'
    
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', NEON_DB_URL)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False
    WTF_CSRF_ENABLED = False   # Disable CSRF temporarily (re-enable in production)
    ITEMS_PER_PAGE = 20
    COMPANY_NAME = "Gas Pinas Inc."
    COMPANY_ADDRESS = "Gas Pinas Inc, Mandaue City, Cebu, Philippines"
    COMPANY_CONTACT = "09XX-XXX-XXXX"
