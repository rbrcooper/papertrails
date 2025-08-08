from flask import Flask, jsonify
import sys
import os

# Add the parent directory to the Python path to allow for package imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from processes.database_handler import DatabaseHandler

app = Flask(__name__)

def get_db():
    """Initializes and returns a DatabaseHandler instance."""
    # This could be expanded to use Flask's g object for per-request connections
    return DatabaseHandler()

@app.route('/')
def index():
    return "Welcome to the Papertrails API!"

@app.route('/api/companies', methods=['GET'])
def get_companies():
    """Returns a JSON list of all company names from the database."""
    try:
        db = get_db()
        company_names = db.get_all_company_names()
        return jsonify(company_names)
    except Exception as e:
        # Log the error properly in a real application
        print(f"Error fetching companies: {e}")
        return jsonify({"error": "Could not retrieve company data"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000) 