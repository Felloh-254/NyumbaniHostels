# Nyumbani Hostels

Nyumbani Hostels is a Python-based hostel management system designed to simplify the administration of hostels. The application helps track tenants, room assignments, and payments, providing an organized and efficient solution for hostel administrators.

## Features

- Manage tenant information (add, edit, delete)
- Track room availability and assignments
- Monitor payments and outstanding balances
- Generate simple reports (optional extension)
- Easy to extend with additional features like notifications and online payment integration

## Tech Stack

- Python
- Flask (optional, if you plan a web interface)
- PostgreSQL for data storage
- `python-dotenv` for environment variable management

## Setup

1. Clone the repository:
git clone https://github.com/USERNAME/nyumbani-hostels.git
cd nyumbani-hostels

2. Create a virtual environment and activate it:

python -m venv venv
# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate

3. Install dependencies:

pip install -r requirements.txt

4. Create a `.env` file in the project root with your environment variables:

DATABASE_URL=postgresql://username:password@localhost:5432/nyumbani
FLASK_APP=app.py
FLASK_ENV=development
SECRET_KEY=your_secret_key_here

5. Run the application:

python app.py

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request for any enhancements or bug fixes.

