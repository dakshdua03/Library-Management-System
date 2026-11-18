from flask import Flask
from app.config import Config
from app.extensions import db

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)

    # Register Blueprints
    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.patrons import patrons_bp
    from app.routes.catalog import catalog_bp
    from app.routes.circulation import circulation_bp
    from app.routes.selfservice import selfservice_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(patrons_bp)
    app.register_blueprint(catalog_bp)
    app.register_blueprint(circulation_bp)
    app.register_blueprint(selfservice_bp)

    return app
