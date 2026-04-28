# LPG Management System

A comprehensive, enterprise-grade web application for managing Liquefied Petroleum Gas (LPG) inventory, consumer relationships, plant movements, and financial transactions. This system is designed to streamline operations for LPG distributors and retailers, ensuring accurate tracking of tanks and efficient transaction processing.

---

## 🚀 Key Features

### 📦 Inventory & Tank Tracking
- **Serial-Level Tracking**: Monitor individual LPG cylinders using unique serial numbers or auto-generated internal codes.
- **Batch Registration**: Quickly add multiple tanks to the system in a single batch.
- **Real-Time Status**: Track tank condition (Full/Empty), location (Warehouse/Plant/Consumer), and category (New/Old).
- **Movement History**: Detailed audit trail for every tank, showing its journey from delivery to refill.

### 👥 Consumer & Relationship Management
- **Profile Management**: Maintain detailed records for consumers, including business names, contact details, and addresses.
- **Financial Overview**: Track credit limits and real-time outstanding balances for every consumer.
- **Transaction Logs**: Easy access to historical sales and returns for specific customers.

### 🏭 Plant & Refill Management
- **Multi-Plant Support**: Manage multiple LPG refilling plants and their contact information.
- **Dynamic Pricing**: Configure refill costs for different tank sizes (11kg, 22kg, 50kg, etc.) per plant.
- **Refill Logistics**: Track movements of empty tanks sent to plants and full tanks received.

### 💰 Transactions & Invoicing
- **Sales & Returns**: Handle complex transactions including cylinder swaps, sales, and returns.
- **Automated Invoicing**: Generate professional invoices with unique tracking numbers.
- **Payment Processing**: Record payments via various methods (Cash, etc.) and manage partially paid invoices.
- **Logistics Integration**: Capture driver names and truck plate numbers for every delivery.

### 📊 Reporting & Analytics
- **Dynamic Dashboard**: Visual overview of key performance indicators and inventory status.
- **Export Capabilities**: Generate detailed reports in **Excel (XLSX)** and **PDF** formats for accounting and auditing.
- **Audit Logs**: Maintain a secure record of all user actions (Create, Update, Delete, Login) for transparency.

---

## 🛠️ System Architecture

The system follows a modular **Model-View-Controller (MVC)** pattern built on a modern Python stack.

### Backend Stack
- **Framework**: [Flask](https://flask.palletsprojects.com/) (Python)
- **Database ORM**: [Flask-SQLAlchemy](https://flask-sqlalchemy.palletsprojects.com/)
- **Security**: [Bcrypt](https://pypi.org/project/bcrypt/) for password hashing and [Flask-Login](https://flask-login.readthedocs.io/) for session management.
- **Form Handling**: [Flask-WTF](https://flask-wtf.readthedocs.io/) for secure form processing and CSRF protection.
- **Reporting**: [ReportLab](https://www.reportlab.com/) (PDF) and [OpenPyXL](https://openpyxl.readthedocs.io/) (Excel).

### Database Schema
- **Users**: RBAC (Role-Based Access Control) with Admin and Staff levels.
- **Consumers**: Integrated with financial tracking.
- **Tanks**: Core inventory unit with status and location tracking.
- **Transactions**: Multi-item sales and movement records.
- **Audit Logs**: Comprehensive system-wide logging.

---

## 📁 Project Structure

```text
LPG SYSTEM/
├── app/                    # Core Application Logic
│   ├── auth/               # Authentication & User Management
│   ├── consumers/          # Consumer Records & Balances
│   ├── dashboard/          # Analytics & Overview
│   ├── plants/             # LPG Plant Management
│   ├── reports/            # PDF/Excel Generation Logic
│   ├── settings/           # System Configuration
│   ├── tanks/              # Inventory & Serial Tracking
│   ├── transactions/       # Sales & Movement Logic
│   ├── models.py           # Database Schema (SQLAlchemy)
│   ├── templates/          # Jinja2 HTML Templates
│   └── static/             # CSS, JS, and Media Assets
├── config.py               # App Configuration
├── run.py                  # Entry Point
├── sync_to_neon.py         # Database Migration/Sync Utility
└── requirements.txt        # Python Dependencies
```

---

## ⚙️ Installation & Setup

### Prerequisites
- Python 3.8+
- PostgreSQL (or Neon.tech for cloud database)

### Setup Steps
1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd "LPG SYSTEM"
   ```

2. **Create a Virtual Environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Configuration**:
   Create a `.env` file based on `.env.example`:
   ```text
   SECRET_KEY=your-secret-key
   DATABASE_URL=postgresql://user:password@localhost/lpg_db
   ```

5. **Initialize Database**:
   The system automatically seeds a default admin account on the first run.
   - **Default Admin**: `admin`
   - **Default Password**: `Admin@1234`

6. **Run the Application**:
   ```bash
   python run.py
   ```

---

## 🔒 Security & Compliance
- **Audit Logging**: Every sensitive action is logged with User ID, Action, Module, and Timestamp.
- **Role-Based Access**: Restrict access to settings and reports based on user roles.
- **Secure Authentication**: Industry-standard Bcrypt hashing for all credentials.

---
© 2024 LPG Management System. All rights reserved.
