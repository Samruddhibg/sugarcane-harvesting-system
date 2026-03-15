import os
import logging
from flask import Flask
from flask_cors import CORS
from db import init_db
from services.scheduler import start_scheduler

# Import Blueprints
from routes.auth import auth_bp
from routes.farmer import farmer_bp
from routes.machine import machine_bp
from routes.factory import factory_bp
from routes.common import common_bp

def create_app():
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    app = Flask(__name__)
    CORS(app)  # Enable CORS for React frontend
    
    # Initialize Database Connection Pool
    init_db()
    
    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(farmer_bp, url_prefix='/api/farmer')
    app.register_blueprint(machine_bp, url_prefix='/api/machine')
    app.register_blueprint(factory_bp, url_prefix='/api/factory')
    app.register_blueprint(common_bp, url_prefix='/api')
    
    logger.info("\n" + "="*70)
    logger.info("🚀 Sugarcane Harvesting System - Full Stack Backend")
    logger.info("="*70)
    
    if os.getenv("FLASK_ENV") != "development":
        start_scheduler()
    
    logger.info("✓ Flask starting on http://0.0.0.0:5000")
    logger.info("="*70 + "\n")
    
    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)